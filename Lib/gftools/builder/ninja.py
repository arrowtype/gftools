"""Ninja file writer for orchestrating font builds"""
from ninja.ninja_syntax import Writer
import ninja
import glyphsLib
from glyphsLib.builder.builders import UFOBuilder
import sys
import ufoLib2
import os
from gftools.builder import GFBuilder
from fontTools.designspaceLib import DesignSpaceDocument
from pathlib import Path

UNSUPPORTED = ["stylespaceFile", "statFormat4", "ttfaUseScript", "vttSources"]


class NinjaBuilder(GFBuilder):
    def build(self):
        # In some cases we want to fall back to GFBuilder
        for unsupported_key in UNSUPPORTED:
            if self.config.get(unsupported_key):
                self.logger.error(
                    "%s configuration parameter not supported by ninja builder, "
                    "falling back to classic GFBuilder" % unsupported_key
                )
                raise NotImplementedError()

        self.w = Writer(open("build.ninja", "w"))
        self.temporaries = []
        self.setup_rules()
        self.get_designspaces()

        if self.config["buildVariable"]:
            self.build_variable()
            # transfer vf vtt hints now in case static fonts are instantiated
            if "vttSources" in self.config:
                self.build_vtt(self.config["vfDir"])
        if self.config["buildStatic"]:
            self.build_static()
            if "vttSources" in self.config:
                self.build_vtt(self.config["ttDir"])
        self.w.close()

        ninja_args = []
        if self.config["logLevel"] == "DEBUG":
            ninja_args = ["-v", "-j", "1"]

        ninja._program("ninja", ninja_args)

        # Tidy up stamp files
        for temporary in self.temporaries:
            if os.file.exists(temporary):
                os.remove(temporary)

    def setup_rules(self):
        self.w.comment("Rules")
        self.w.newline()
        self.w.comment("Convert glyphs file to UFO")
        self.w.rule("glyphs2ufo", "fontmake -o ufo -g $in")

        if self.config["buildVariable"]:
            self.w.comment("Build a variable font from Designspace")
            self.w.rule("variable", "fontmake -o variable -m $in $fontmake_args")

        self.w.comment("Build a set of instance UFOs from Designspace")
        self.w.rule("instanceufo", "fontmake -i -o ufo -m $in $fontmake_args")

        self.w.comment("Build a TTF file from a UFO")
        self.w.rule(
            "buildttf", "fontmake -o ttf -u $in $fontmake_args --output-path $out"
        )

        self.w.comment("Build an OTF file from a UFO")
        self.w.rule(
            "buildotf", "fontmake -o otf -u $in $fontmake_args --output-path $out"
        )

        self.w.comment("Add a STAT table to a set of variable fonts")
        self.w.rule(
            "genstat",
            "gftools-gen-stat.py --inplace $other_args --axis-order $axis_order -- $in  && touch $stampfile",
        )

        self.w.comment("Run the font fixer in-place and touch a stamp file")
        self.w.rule(
            "fix", "gftools-fix-font.py -o $in $fixargs $in && touch $in.fixstamp"
        )

        self.w.comment("Run the ttfautohint in-place and touch a stamp file")
        self.w.rule(
            "autohint",
            "ttfautohint $in $in.autohinted && mv $in.autohinted $in && touch $in.autohintstamp",
        )

        self.w.comment("Create a web font")
        self.w.rule("webfont", f"fonttools ttLib.woff2 compress -o $out $in")

        self.w.newline()

    def get_designspaces(self):
        self.designspaces = []
        for source in self.config["sources"]:
            if source.endswith(".glyphs"):
                builder = UFOBuilder(glyphsLib.GSFont(source))
                # This is a sneaky way of skipping the hard work of
                # converting all the glyphs and stuff, and just gettting
                # a minimal designspace
                builder.to_ufo_groups = (
                    builder.to_ufo_kerning
                ) = builder.to_ufo_layers = lambda: True

                designspace = builder.designspace
                designspace_path = os.path.join("master_ufo", designspace.filename)
                os.makedirs(os.path.dirname(designspace_path), exist_ok=True)
                designspace.write(designspace_path)
                self.w.comment("Convert glyphs source to designspace")
                designspace_and_ufos = [designspace_path] + list(
                    set(
                        [
                            os.path.join("master_ufo", m.filename)
                            for m in designspace.sources
                        ]
                    )
                )
                self.w.build(designspace_and_ufos, "glyphs2ufo", source)
            else:
                designspace_path = source
                designspace = DesignSpaceDocument.fromfile(designspace_path)
            self.designspaces.append((designspace_path, designspace))
        self.w.newline()

    def fontmake_args(self, args):
        my_args = []
        my_args.append("--filter ...")
        if self.config["flattenComponents"]:
            my_args.append("--filter FlattenComponentsFilter")
        if self.config["decomposeTransformedComponents"]:
            my_args.append("--filter DecomposeTransformedComponentsFilter")
        if "output_dir" in args:
            my_args.append("--output-dir " + args["output_dir"])
        if "output_path" in args:
            my_args.append("--output-path " + args["output_path"])
        return " ".join(my_args)

    def build_variable(self):
        targets = []
        self.w.newline()
        self.w.comment("VARIABLE FONTS")
        self.w.newline()
        for (designspace_path, designspace) in self.designspaces:
            axis_tags = sorted([ax.tag for ax in designspace.axes])
            axis_tags = ",".join(axis_tags)
            target = os.path.join(
                self.config["vfDir"],
                Path(designspace_path).stem + "[%s].ttf" % axis_tags,
            )
            self.w.build(
                target,
                "variable",
                designspace_path,
                variables={
                    "fontmake_args": self.fontmake_args({"output_path": target})
                },
            )
            targets.append(target)
        self.w.newline()
        stampfile = self.gen_stat(axis_tags, targets)
        # We post process each variable font after generating the STAT tables
        # because these tables are needed in order to fix the name tables.
        self.w.comment("Variable font post-processing")
        for t in targets:
            self.post_process(t, implicit=stampfile)

    def gen_stat(self, axis_tags, targets):
        self.w.comment("Generate STAT tables")
        if "axisOrder" not in self.config:
            self.config["axisOrder"] = axis_tags.split(",")
            # Janky "is-italic" test. To strengthen this up we should look inside
            # the source files and check their stylenames.
            if any("italic" in x[0].lower() for x in self.designspaces):
                self.config["axisOrder"].append("ital")
        other_args = ""
        if "stat" in self.config:
            other_args = f"--src {self.config['stat']}"
        if "stylespaceFile" in self.config or "statFormat4" in self.config:
            raise ValueError(
                "Stylespace files / statFormat4 not supported in Ninja mode"
            )
            # Because gftools-gen-stat doesn't seem to support it?
        stampfile = targets[0] + ".statstamp"
        self.temporaries.append(stampfile)
        self.w.build(
            stampfile,
            "genstat",
            targets,
            variables={
                "axis_order": self.config["axisOrder"],
                "other_args": other_args,
                "stampfile": stampfile,
            },
        )
        self.w.newline()
        return stampfile

    def post_process(self, file, implicit=None):
        variables = {}
        if self.config["includeSourceFixes"]:
            variables = {"fixargs": "--include-source-fixes"}
        self.temporaries.append(file + ".fixstamp")
        self.w.build(
            file + ".fixstamp", "fix", file, implicit=implicit, variables=variables
        )

    def _instance_ufo_filenames(self, path, designspace):
        instance_filenames = []
        for instance in designspace.instances:
            fn = instance.filename
            if "/" in fn:
                ufo = Path(fn)
            else:
                ufo = Path(path).parent / fn
            instance_filenames.append(ufo)
        return instance_filenames

    def build_static(self):
        # Let's make our interpolated UFOs.
        self.w.newline()
        self.w.comment("STATIC FONTS")
        self.w.newline()
        for (path, designspace) in self.designspaces:
            self.w.comment(f"  Interpolate UFOs for {os.path.basename(path)}")

            self.w.build(
                [str(i) for i in self._instance_ufo_filenames(path, designspace)],
                "instanceufo",
                path,
            )
            self.w.newline()

        return GFBuilder.build_static(self)

    def instantiate_static_fonts(self, directory, postprocessor):
        pass

    def build_a_static_format(self, format, directory, postprocessor):
        self.w.comment(f"Build {format} format")
        self.w.newline()
        if format == "ttf":
            target_dir = self.config["ttDir"]
        else:
            target_dir = self.config["otDir"]
        targets = []
        for (path, designspace) in self.designspaces:
            self.w.comment(f" {path}")
            for ufo in self._instance_ufo_filenames(path, designspace):
                target = str(Path(target_dir) / ufo.with_suffix(f".{format}").name)
                self.w.build(target, "build" + format, str(ufo), variables={
                    "fontmake_args": self.fontmake_args({"output_path": target})
                })
                targets.append(target)
        self.w.newline()
        self.w.comment(f"Post-processing {format}s")
        for t in targets:
            postprocessor(t)
        self.w.newline()

    def post_process_ttf(self, filename):
        if self.config["autohintTTF"]:
            if self.config["ttfaUseScript"]:
                raise NotImplementedError("ttaUseScript not supported in ninja mode")
            self.w.build(filename + ".autohintstamp", "autohint", filename)
            self.temporaries.append(filename + ".autohintstamp")
            self.post_process(filename, implicit=filename + ".autohintstamp")
        else:
            self.post_process(filename)
        if self.config["buildWebfont"]:
            webfont_filename = filename.replace(".ttf", ".woff2").replace(
                self.config["ttDir"], self.config["woffDir"]
            )
            self.w.build(
                webfont_filename, "webfont", filename, implicit=filename + ".fixstamp"
            )

    def build_vtt(self, font_dir):
        # This should be an external gftool
        raise NotImplementedError


if __name__ == "__main__":
    NinjaBuilder(sys.argv[1]).build()

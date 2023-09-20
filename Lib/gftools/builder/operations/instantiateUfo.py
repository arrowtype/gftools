from typing import List
from gftools.builder.file import File
from gftools.builder.operations import FontmakeOperationBase
import glyphsLib
import os
import gftools.builder
from functools import cached_property
from glyphsLib.builder import UFOBuilder
from fontTools.designspaceLib import InstanceDescriptor


class InstantiateUFO(FontmakeOperationBase):
    description = "Create instance UFOs from a Glyphs or designspace file"
    rule = "fontmake -i \"$instance_name\" -o ufo $fontmake_type $in $fontmake_args"

    def validate(self):
        # Ensure there is an instance name
        if "instance_name" not in self.original:
            raise ValueError("No instance name specified")
        # Ensure the instance is defined in the font
        desired = self.original["instance_name"]
        if "target" not in self.original and not self.relevant_instance:
            raise ValueError(
                f"Instance {desired} not found in {self.first_source.path}"
            )
    
    @cached_property
    def relevant_instance(self) -> InstanceDescriptor | None:
        desired = self.original["instance_name"]
        relevant_instance = [i for i in self.first_source.instances if i.name == desired]
        if len(relevant_instance) == 0:
            return None
        return relevant_instance[0]
        
    @property
    def targets(self):
        if "target" in self.original:
            return [ File(self.original["target"]) ]
        instance = self.relevant_instance
        assert instance is not None
        assert instance.filename is not None
        if self.first_source.is_glyphs:
            return [ File("instance_ufos/"+os.path.basename(instance.filename)) ]
        return [ File(instance.filename) ]

    @property
    def variables(self):
        vars = super().variables
        if self.first_source.is_glyphs:
            vars["fontmake_args"] += "--instance-dir instance_ufos/ "
        vars["instance_name"] = self.original["instance_name"]
        return vars
    
    def set_target(self, target: File):
        raise ValueError("Cannot set target on InstantiateUFO")

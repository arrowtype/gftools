"""
This schema represents all known key/value pairs for the builder config file.
"""
from strictyaml import (
                        Map,
                        MapPattern,
                        Str,
                        Int,
                        Float,
                        Seq,
                        Optional,
                        Bool,
                        UniqueSeq,
                        Enum,
                        Any
                        )
from gftools.packager import CATEGORIES


stat_schema = Seq(
    Map({
        "name": Str(),
        "tag": Str(),
        "values": Seq(
            Map({
                "name": Str(),
                "value": Int() | Float(),
                Optional("nominalValue"): Int() | Float(),
                Optional("linkedValue"): Int() | Float(),
                Optional("rangeMinValue"): Int() | Float(),
                Optional("rangeMaxValue"): Int() | Float(),
                Optional("flags"): Int()
            })
        )
    }),
)

stat_format4_schema = Seq(
    Map({
        "name": Str(),
        Optional("flags"): Int(),
        "location": MapPattern(Str(), Int() | Float()),
    })
)

schema = Map(
    {
        Optional("recipe"): MapPattern(Str(), Seq(Any())),
        Optional("recipeProvider"): Str(),
        "sources": Seq(Str()),
        Optional("vttSources"): MapPattern(Str(), Str()),
        Optional("fvarInstanceAxisDflts"): MapPattern(Str(), Float()),
        Optional("logLevel"): Str(),
        Optional("stat"): stat_schema | MapPattern(Str(), stat_schema),
        Optional("statFormat4"): stat_format4_schema | MapPattern(Str(), stat_format4_schema),
        Optional("familyName"): Str(),
        Optional("includeSourceFixes"): Bool(),
        Optional("stylespaceFile"): Str(),
        Optional("buildVariable"): Bool(),
        Optional("buildStatic"): Bool(),
        Optional("buildOTF"): Bool(),
        Optional("buildTTF"): Bool(),
        Optional("buildWebfont"): Bool(),
        Optional("outputDir"): Str(),
        Optional("vfDir"): Str(),
        Optional("ttDir"): Str(),
        Optional("otDir"): Str(),
        Optional("woffDir"): Str(),
        Optional("cleanUp"): Bool(),
        Optional("autohintTTF"): Bool(),
        Optional("autohintOTF"): Bool(),
        Optional("axisOrder"): Seq(Str()),
        Optional("flattenComponents"): Bool(),
        Optional("decomposeTransformedComponents"): Bool(),
        Optional("ttfaUseScript"): Bool(),
        Optional("googleFonts"): Bool(),
        Optional("category"): UniqueSeq(Enum(CATEGORIES)),
        Optional("reverseOutlineDirection"): Bool(),
        Optional("interpolate"): Bool(),
        Optional("checkCompatibility"): Bool(),
        Optional("removeOutlineOverlaps"): Bool(),
        Optional("expandFeaturesToInstances"): Bool(),
        Optional("version"): Str(),
        Optional("addGftoolsVersion"): Bool(),
        Optional("glyphData"): Seq(Str()),
    }
)

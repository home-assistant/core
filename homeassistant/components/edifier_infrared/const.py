"""Constants for the Edifier infrared integration."""

from enum import StrEnum

from infrared_protocols.codes.edifier.r1280db import EdifierR1280DBCode
from infrared_protocols.codes.edifier.r1280t import EdifierR1280TCode
from infrared_protocols.codes.edifier.r1700bt import EdifierR1700BTCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
from infrared_protocols.codes.edifier.s360db import EdifierS360DBCode

DOMAIN = "edifier_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_COMMAND_SET = "command_set"

type EdifierCode = (
    EdifierR1700BTCode
    | EdifierR1280DBCode
    | EdifierR1280TCode
    | EdifierS360DBCode
    | EdifierRC20GCode
)


class EdifierCommandSets(StrEnum):
    """Edifier command set groupings."""

    R1700BT = "r1700bt"
    R1280DB = "r1280db"
    R1280T = "r1280t"
    S360DB = "s360db"
    RC20G = "rc20g"


class EdifierModel(StrEnum):
    """Edifier speaker models."""

    # R1700BT command set
    R1700BT = "R1700BT"
    R1700BTS = "R1700BTs"
    RC17A = "RC17A"
    RC80B = "RC80B"
    R1855DB = "R1855DB"
    # R1280DB command set
    R1280DB = "R1280DB"
    R2730DB = "R2730DB"
    RC10D1 = "RC10D1"
    R2000DB = "R2000DB"
    # R1280T command set (basic)
    R1280T = "R1280T"
    # S360DB command set
    S360DB = "S360DB"
    RC31A = "RC31A"
    # RC20G command set (unique left/right volume controls)
    RC20G = "RC20G"


MODEL_TO_COMMAND_SET: dict[EdifierModel, EdifierCommandSets] = {
    # R1700BT command set
    EdifierModel.R1700BT: EdifierCommandSets.R1700BT,
    EdifierModel.R1700BTS: EdifierCommandSets.R1700BT,
    EdifierModel.RC17A: EdifierCommandSets.R1700BT,
    EdifierModel.RC80B: EdifierCommandSets.R1700BT,
    EdifierModel.R1855DB: EdifierCommandSets.R1700BT,
    # R1280DB command set
    EdifierModel.R1280DB: EdifierCommandSets.R1280DB,
    EdifierModel.R2730DB: EdifierCommandSets.R1280DB,
    EdifierModel.RC10D1: EdifierCommandSets.R1280DB,
    EdifierModel.R2000DB: EdifierCommandSets.R1280DB,
    # R1280T command set
    EdifierModel.R1280T: EdifierCommandSets.R1280T,
    # S360DB command set
    EdifierModel.S360DB: EdifierCommandSets.S360DB,
    EdifierModel.RC31A: EdifierCommandSets.S360DB,
    # RC20G command set
    EdifierModel.RC20G: EdifierCommandSets.RC20G,
}

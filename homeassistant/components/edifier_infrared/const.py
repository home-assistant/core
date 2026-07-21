"""Constants for the Edifier infrared integration."""

from infrared_protocols.codes.edifier.r1280db import EdifierR1280DBCode
from infrared_protocols.codes.edifier.r1280t import EdifierR1280TCode
from infrared_protocols.codes.edifier.r1700bt_pre_2017 import EdifierR1700BTPre2017Code
from infrared_protocols.codes.edifier.r1700bts import EdifierR1700BTsCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
from infrared_protocols.codes.edifier.s360db import EdifierS360DBCode
from infrared_protocols.codes.edifier.s3000pro import EdifierS3000ProCode

DOMAIN = "edifier_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_COMMAND_SET = "command_set"

type EdifierCode = (
    EdifierR1700BTPre2017Code
    | EdifierR1700BTsCode
    | EdifierR1280DBCode
    | EdifierR1280TCode
    | EdifierS360DBCode
    | EdifierRC20GCode
    | EdifierS3000ProCode
)

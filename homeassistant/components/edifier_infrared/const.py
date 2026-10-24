"""Constants for the Edifier infrared integration."""

from infrared_protocols.codes.edifier.models import EdifierCommandSet
from infrared_protocols.codes.edifier.r1280db import EdifierR1280DBCode
from infrared_protocols.codes.edifier.r1280t import EdifierR1280TCode
from infrared_protocols.codes.edifier.r1380db import EdifierR1380DBCode
from infrared_protocols.codes.edifier.r1700bt_2017 import EdifierR1700BT2017Code
from infrared_protocols.codes.edifier.r1700bt_pre_2017 import EdifierR1700BTPre2017Code
from infrared_protocols.codes.edifier.r1700bts import EdifierR1700BTsCode
from infrared_protocols.codes.edifier.r2000db import EdifierR2000DBCode
from infrared_protocols.codes.edifier.r2730db import EdifierR2730DBCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
from infrared_protocols.codes.edifier.s360db import EdifierS360DBCode
from infrared_protocols.codes.edifier.s3000pro import EdifierS3000ProCode

DOMAIN = "edifier_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_COMMAND_SET = "command_set"
SUPPORTED_COMMAND_SETS = [
    EdifierCommandSet.R1280DB,
    EdifierCommandSet.R1280T,
    EdifierCommandSet.R1380DB,
    EdifierCommandSet.R1700BTS,
    EdifierCommandSet.R1700BT_2017,
    EdifierCommandSet.R1700BT_PRE_2017,
    EdifierCommandSet.R2000DB,
    EdifierCommandSet.R2730DB,
    EdifierCommandSet.RC20G,
    EdifierCommandSet.S3000PRO,
    EdifierCommandSet.S360DB,
]

type EdifierCode = (
    EdifierR1700BTPre2017Code
    | EdifierR1700BT2017Code
    | EdifierR1700BTsCode
    | EdifierR1280DBCode
    | EdifierR1280TCode
    | EdifierR1380DBCode
    | EdifierR2000DBCode
    | EdifierR2730DBCode
    | EdifierS360DBCode
    | EdifierRC20GCode
    | EdifierS3000ProCode
)

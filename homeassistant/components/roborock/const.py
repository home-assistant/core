"""Constants for Roborock."""
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN

DOMAIN = "roborock"
CONF_ENTRY_CODE = "code"
CONF_BASE_URL = "base_url"
CONF_USER_DATA = "user_data"
DEFAULT_NAME = DOMAIN

VACUUM = VACUUM_DOMAIN
PLATFORMS = [VACUUM]

ROCKROBO_V1 = "rockrobo.vacuum.v1"
ROCKROBO_S4 = "roborock.vacuum.s4"
ROCKROBO_S4_MAX = "roborock.vacuum.a19"
ROCKROBO_S5 = "roborock.vacuum.s5"
ROCKROBO_S5_MAX = "roborock.vacuum.s5e"
ROCKROBO_S6 = "roborock.vacuum.s6"
ROCKROBO_T6 = "roborock.vacuum.t6"  # cn s6
ROCKROBO_E4 = "roborock.vacuum.a01"
ROCKROBO_S6_PURE = "roborock.vacuum.a08"
ROCKROBO_T7 = "roborock.vacuum.a11"  # cn s7
ROCKROBO_T7S = "roborock.vacuum.a14"
ROCKROBO_T7SPLUS = "roborock.vacuum.a23"
ROCKROBO_S7_MAXV = "roborock.vacuum.a27"
ROCKROBO_S7_PRO_ULTRA = "roborock.vacuum.a62"
ROCKROBO_Q5 = "roborock.vacuum.a34"
ROCKROBO_Q7_MAX = "roborock.vacuum.a38"
ROCKROBO_G10S = "roborock.vacuum.a46"
ROCKROBO_G10 = "roborock.vacuum.a29"
ROCKROBO_S7 = "roborock.vacuum.a15"
ROCKROBO_S6_MAXV = "roborock.vacuum.a10"
ROCKROBO_E2 = "roborock.vacuum.e2"
ROCKROBO_1S = "roborock.vacuum.m1s"
ROCKROBO_C1 = "roborock.vacuum.c1"
ROCKROBO_WILD = "roborock.vacuum.*"  # wildcard

MODELS_VACUUM_WITH_MOP = [
    ROCKROBO_E2,
    ROCKROBO_S5,
    ROCKROBO_S5_MAX,
    ROCKROBO_S6,
    ROCKROBO_S6_MAXV,
    ROCKROBO_S6_PURE,
    ROCKROBO_S7,
    ROCKROBO_S7_MAXV,
]
MODELS_VACUUM_WITH_SEPARATE_MOP = [
    ROCKROBO_S7,
    ROCKROBO_S7_MAXV,
]
CONF_INCLUDE_SHARED = "include_shared"

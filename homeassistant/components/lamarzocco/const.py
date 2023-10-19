"""Constants for the La Marzocco integration."""

from typing import Final

DOMAIN: Final = "lamarzocco"

POLLING_INTERVAL: Final = 30
UPDATE_DELAY: Final = 3

DEFAULT_CLIENT_ID: Final = "7_1xwei9rtkuckso44ks4o8s0c0oc4swowo00wgw0ogsok84kosg"
DEFAULT_CLIENT_SECRET: Final = "2mgjqpikbfuok8g4s44oo4gsw0ks44okk4kc4kkkko0c8soc8s"

DEFAULT_PORT_LOCAL: Final = 8081

MODEL_GS3_AV: Final = "GS3 AV"
MODEL_GS3_MP: Final = "GS3 MP"
MODEL_LM: Final = "Linea Mini"
MODEL_LMU: Final = "Micra"

BREW_ACTIVE: Final = "brew_active"

GLOBAL: Final = "global"
MON: Final = "mon"
TUE: Final = "tue"
WED: Final = "wed"
THU: Final = "thu"
FRI: Final = "fri"
SAT: Final = "sat"
SUN: Final = "sun"

DAYS: Final = [MON, TUE, WED, THU, FRI, SAT, SUN]

MACHINE_NAME: Final = "machine_name"
SERIAL_NUMBER: Final = "serial_number"

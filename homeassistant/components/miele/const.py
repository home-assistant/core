"""Constants for the Miele integration."""

from enum import IntEnum

DOMAIN = "miele"
MANUFACTURER = "Miele"

ACTIONS = "actions"
POWER_ON = "powerOn"
POWER_OFF = "powerOff"
PROCESS_ACTION = "processAction"


class MieleAppliance(IntEnum):
    """Define appliance types."""

    WASHING_MACHINE = 1
    TUMBLE_DRYER = 2
    WASHING_MACHINE_SEMI_PROFESSIONAL = 3
    TUMBLE_DRYER_SEMI_PROFESSIONAL = 4
    WASHING_MACHINE_PROFESSIONAL = 5
    DRYER_PROFESSIONAL = 6
    DISHWASHER = 7
    DISHWASHER_SEMI_PROFESSIONAL = 8
    DISHWASHER_PROFESSIONAL = 9
    OVEN = 12
    OVEN_MICROWAVE = 13
    HOB_HIGHLIGHT = 14
    STEAM_OVEN = 15
    MICROWAVE = 16
    COFFEE_SYSTEM = 17
    HOOD = 18
    FRIDGE = 19
    FREEZER = 20
    FRIDGE_FREEZER = 21
    ROBOT_VACUUM_CLEANER = 23
    WASHER_DRYER = 24
    DISH_WARMER = 25
    HOB_INDUCTION = 27
    STEAM_OVEN_COMBI = 31
    WINE_CABINET = 32
    WINE_CONDITIONING_UNIT = 33
    WINE_STORAGE_CONDITIONING_UNIT = 34
    STEAM_OVEN_MICRO = 45
    DIALOG_OVEN = 67
    WINE_CABINET_FREEZER = 68
    STEAM_OVEN_MK2 = 73
    HOB_INDUCT_EXTR = 74


class StateStatus(IntEnum):
    """Define appliance states."""

    RESERVED = 0
    OFF = 1
    ON = 2
    PROGRAMMED = 3
    WAITING_TO_START = 4
    RUNNING = 5
    PAUSE = 6
    PROGRAM_ENDED = 7
    FAILURE = 8
    PROGRAM_INTERRUPTED = 9
    IDLE = 10
    RINSE_HOLD = 11
    SERVICE = 12
    SUPERFREEZING = 13
    SUPERCOOLING = 14
    SUPERHEATING = 15
    SUPERCOOLING_SUPERFREEZING = 146
    AUTOCLEANING = 147
    NOT_CONNECTED = 255


STATE_STATUS_TAGS = {
    StateStatus.OFF: "off",
    StateStatus.ON: "on",
    StateStatus.PROGRAMMED: "programmed",
    StateStatus.WAITING_TO_START: "waiting_to_start",
    StateStatus.RUNNING: "running",
    StateStatus.PAUSE: "pause",
    StateStatus.PROGRAM_ENDED: "program_ended",
    StateStatus.FAILURE: "failure",
    StateStatus.PROGRAM_INTERRUPTED: "program_interrupted",
    StateStatus.IDLE: "idle",
    StateStatus.RINSE_HOLD: "rinse_hold",
    StateStatus.SERVICE: "service",
    StateStatus.SUPERFREEZING: "superfreezing",
    StateStatus.SUPERCOOLING: "supercooling",
    StateStatus.SUPERHEATING: "superheating",
    StateStatus.SUPERCOOLING_SUPERFREEZING: "supercooling_superfreezing",
    StateStatus.AUTOCLEANING: "autocleaning",
    StateStatus.NOT_CONNECTED: "not_connected",
}


class MieleActions(IntEnum):
    """Define appliance actions."""

    START = 1
    STOP = 2
    PAUSE = 3
    START_SUPERFREEZE = 4
    STOP_SUPERFREEZE = 5
    START_SUPERCOOL = 6
    STOP_SUPERCOOL = 7


# Possible actions
PROCESS_ACTIONS = {
    "start": MieleActions.START,
    "stop": MieleActions.STOP,
    "pause": MieleActions.PAUSE,
    "start_superfreezing": MieleActions.START_SUPERFREEZE,
    "stop_superfreezing": MieleActions.STOP_SUPERFREEZE,
    "start_supercooling": MieleActions.START_SUPERCOOL,
    "stop_supercooling": MieleActions.STOP_SUPERCOOL,
}

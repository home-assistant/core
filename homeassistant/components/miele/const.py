"""Constants for the Miele integration."""

from enum import IntEnum

DOMAIN = "miele"
MANUFACTURER = "Miele"

ACTIONS = "actions"
POWER_ON = "powerOn"
POWER_OFF = "powerOff"
PROCESS_ACTION = "processAction"
VENTILATION_STEP = "ventilationStep"
DISABLED_TEMP_ENTITIES = (
    -32768 / 100,
    -32766 / 100,
)
AMBIENT_LIGHT = "ambientLight"
LIGHT = "light"
LIGHT_ON = 1
LIGHT_OFF = 2


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


DEVICE_TYPE_TAGS = {
    MieleAppliance.WASHING_MACHINE: "washing_machine",
    MieleAppliance.TUMBLE_DRYER: "tumble_dryer",
    MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL: "washing_machine",
    MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL: "tumble_dryer",
    MieleAppliance.WASHING_MACHINE_PROFESSIONAL: "washing_machine",
    MieleAppliance.DRYER_PROFESSIONAL: "tumble_dryer",
    MieleAppliance.DISHWASHER: "dishwasher",
    MieleAppliance.DISHWASHER_SEMI_PROFESSIONAL: "dishwasher",
    MieleAppliance.DISHWASHER_PROFESSIONAL: "dishwasher",
    MieleAppliance.OVEN: "oven",
    MieleAppliance.OVEN_MICROWAVE: "oven_microwave",
    MieleAppliance.HOB_HIGHLIGHT: "hob",
    MieleAppliance.STEAM_OVEN: "steam_oven",
    MieleAppliance.MICROWAVE: "microwave",
    MieleAppliance.COFFEE_SYSTEM: "coffee_system",
    MieleAppliance.HOOD: "hood",
    MieleAppliance.FRIDGE: "refrigerator",
    MieleAppliance.FREEZER: "freezer",
    MieleAppliance.FRIDGE_FREEZER: "fridge_freezer",
    MieleAppliance.ROBOT_VACUUM_CLEANER: "robot_vacuum_cleaner",
    MieleAppliance.WASHER_DRYER: "washer_dryer",
    MieleAppliance.DISH_WARMER: "warming_drawer",
    MieleAppliance.HOB_INDUCTION: "hob",
    MieleAppliance.STEAM_OVEN_COMBI: "steam_oven_combi",
    MieleAppliance.WINE_CABINET: "wine_cabinet",
    MieleAppliance.WINE_CONDITIONING_UNIT: "wine_conditioning_unit",
    MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT: "wine_unit",
    MieleAppliance.STEAM_OVEN_MICRO: "steam_oven_micro",
    MieleAppliance.DIALOG_OVEN: "dialog_oven",
    MieleAppliance.WINE_CABINET_FREEZER: "wine_cabinet_freezer",
    MieleAppliance.STEAM_OVEN_MK2: "steam_oven",
    MieleAppliance.HOB_INDUCT_EXTR: "hob_extraction",
}


class StateStatus(IntEnum):
    """Define appliance states."""

    RESERVED = 0
    OFF = 1
    ON = 2
    PROGRAMMED = 3
    WAITING_TO_START = 4
    IN_USE = 5
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
    StateStatus.IN_USE: "in_use",
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

"""Constants for the Miele integration."""

from enum import IntEnum

from pymiele import MieleEnum

DOMAIN = "miele"
MANUFACTURER = "Miele"

ACTIONS = "actions"
POWER_ON = "powerOn"
POWER_OFF = "powerOff"
PROCESS_ACTION = "processAction"
PROGRAM_ID = "programId"
VENTILATION_STEP = "ventilationStep"
TARGET_TEMPERATURE = "targetTemperature"
AMBIENT_LIGHT = "ambientLight"
LIGHT = "light"
LIGHT_ON = 1
LIGHT_OFF = 2

DISABLED_TEMP_ENTITIES = (
    -32768 / 100,
    -32766 / 100,
)


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


class ProgramPhaseWashingMachine(MieleEnum):
    """Program phase codes for washing machines."""

    not_running = 0, 256, 65535
    pre_wash = 257, 259
    soak = 258
    main_wash = 260
    rinse = 261
    rinse_hold = 262
    cleaning = 263
    cooling_down = 264
    drain = 265
    spin = 266
    anti_crease = 267
    finished = 268
    venting = 269
    starch_stop = 270
    freshen_up_and_moisten = 271
    steam_smoothing = 272, 295
    hygiene = 279
    drying = 280
    disinfecting = 285
    unknown_code = -9999


class ProgramPhaseTumbleDryer(MieleEnum):
    """Program phase codes for tumble dryers."""

    not_running = 0, 512, 535, 536, 537, 65535
    program_running = 513
    drying = 514
    machine_iron = 515
    hand_iron_2 = 516
    normal = 517
    normal_plus = 518
    cooling_down = 519
    hand_iron_1 = 520
    anti_crease = 521
    finished = 522
    extra_dry = 523
    hand_iron = 524
    moisten = 526
    thermo_spin = 527
    timed_drying = 528
    warm_air = 529
    steam_smoothing = 530
    comfort_cooling = 531
    rinse_out_lint = 532
    rinses = 533
    smoothing = 534
    slightly_dry = 538
    safety_cooling = 539
    unknown_code = -9999


class ProgramPhaseWasherDryer(MieleEnum):
    """Program phase codes for washer/dryer machines."""

    not_running = 0, 256, 512, 535, 536, 537, 65535
    pre_wash = 257, 259
    soak = 258
    main_wash = 260
    rinse = 261
    rinse_hold = 262
    cleaning = 263
    cooling_down = 264, 519
    drain = 265
    spin = 266
    anti_crease = 267, 521
    finished = (
        268,
        522,
    )
    venting = 269
    starch_stop = 270
    freshen_up_and_moisten = 271
    steam_smoothing = 272, 295, 530
    hygiene = 279
    drying = 280, 514
    disinfecting = 285

    program_running = 513
    machine_iron = 515
    hand_iron_2 = 516
    normal = 517
    normal_plus = 518
    hand_iron_1 = 520
    extra_dry = 523
    hand_iron = 524
    moisten = 526
    thermo_spin = 527
    timed_drying = 528
    warm_air = 529
    comfort_cooling = 531
    rinse_out_lint = 532
    rinses = 533
    smoothing = 534
    slightly_dry = 538
    safety_cooling = 539
    unknown_code = -9999


class ProgramPhaseDishwasher(MieleEnum):
    """Program phase codes for dishwashers."""

    not_running = 1792, 65535
    reactivating = 1793
    pre_dishwash = 1794, 1801
    main_dishwash = 1795
    rinse = 1796
    interim_rinse = 1797
    final_rinse = 1798
    drying = 1799
    finished = 1800
    unknown = -9999


class ProgramPhaseOven(MieleEnum):
    """Program phase codes for ovens."""

    not_running = 0, 65535
    heating_up = 3073
    process_running = 3074
    process_finished = 3078
    energy_save = 3084
    unknown = -9999


class ProgramPhaseWarmingDrawer(MieleEnum):
    """Program phase codes for warming drawers."""

    not_running = 0, 65535
    heating_up = 3073
    door_open = 3075
    keeping_warm = 3094
    cooling_down = 3088


class ProgramPhaseMicrowave(MieleEnum):
    """Program phase for microwave units."""

    not_running = 0, 65535
    heating = 3329
    process_running = 3330
    process_finished = 3334
    energy_save = 3340
    unknown = -9999


class ProgramPhaseCoffeeSystem(MieleEnum):
    """Program phase codes for coffee systems."""

    not_running = 0, 4352, 65535
    heating_up = 3073
    espresso = 4353
    hot_milk = 4354
    milk_foam = 4355
    dispensing = 4361, 4404
    pre_brewing = 4369
    grinding = 4377
    second_espresso = 4385
    second_pre_brewing = 4393
    second_grinding = 4401
    rinse = 4405


class ProgramPhaseRobotVacuumCleaner(MieleEnum):
    """Program phase codes for robot vacuum cleaner."""

    not_running = 0, 65535
    vacuum_cleaning = 5889
    returning = 5890
    vacuum_cleaning_paused = 5891
    going_to_target_area = 5892
    wheel_lifted = 5893  # F1
    dirty_sensors = 5894  # F2
    dust_box_missing = 5895  # F3
    blocked_drive_wheels = 5896  # F4
    blocked_brushes = 5897  # F5
    motor_overload = 5898  # F6
    internal_fault = 5899  # F7
    blocked_front_wheel = 5900  # F8
    docked = 5903, 5904
    remote_controlled = 5910


class ProgramPhaseMicrowaveOvenCombo(MieleEnum):
    """Program phase codes for microwave oven combo."""

    not_running = 0, 65535
    steam_reduction = 3863
    process_running = 7938
    waiting_for_start = 7939
    heating_up_phase = 7940
    process_finished = 7942


PROGRAM_PHASE: dict[int, type[MieleEnum]] = {
    MieleAppliance.WASHING_MACHINE: ProgramPhaseWashingMachine,
    MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL: ProgramPhaseWashingMachine,
    MieleAppliance.WASHING_MACHINE_PROFESSIONAL: ProgramPhaseWashingMachine,
    MieleAppliance.TUMBLE_DRYER: ProgramPhaseTumbleDryer,
    MieleAppliance.DRYER_PROFESSIONAL: ProgramPhaseTumbleDryer,
    MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL: ProgramPhaseTumbleDryer,
    MieleAppliance.WASHER_DRYER: ProgramPhaseWasherDryer,
    MieleAppliance.DISHWASHER: ProgramPhaseDishwasher,
    MieleAppliance.DISHWASHER_SEMI_PROFESSIONAL: ProgramPhaseDishwasher,
    MieleAppliance.DISHWASHER_PROFESSIONAL: ProgramPhaseDishwasher,
    MieleAppliance.OVEN: ProgramPhaseOven,
    MieleAppliance.OVEN_MICROWAVE: ProgramPhaseMicrowaveOvenCombo,
    MieleAppliance.STEAM_OVEN: ProgramPhaseOven,
    MieleAppliance.DIALOG_OVEN: ProgramPhaseOven,
    MieleAppliance.MICROWAVE: ProgramPhaseMicrowave,
    MieleAppliance.COFFEE_SYSTEM: ProgramPhaseCoffeeSystem,
    MieleAppliance.ROBOT_VACUUM_CLEANER: ProgramPhaseRobotVacuumCleaner,
}


class StateProgramType(MieleEnum):
    """Defines program types."""

    normal_operation_mode = 0
    own_program = 1
    automatic_program = 2
    cleaning_care_program = 3
    maintenance_program = 4
    unknown = -9999


class StateDryingStep(MieleEnum):
    """Defines drying steps."""

    extra_dry = 0
    normal_plus = 1
    normal = 2
    slightly_dry = 3
    hand_iron_1 = 4
    hand_iron_2 = 5
    machine_iron = 6
    smoothing = 7
    unknown = -9999


WASHING_MACHINE_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Extrapolated from other device types.
    0: "no_program",  # Returned by the API when no program is selected.
    1: "cottons",
    3: "minimum_iron",
    4: "delicates",
    8: "woollens",
    9: "silks",
    17: "starch",
    18: "rinse",
    21: "drain_spin",
    22: "curtains",
    23: "shirts",
    24: "denim",
    27: "proofing",
    29: "sportswear",
    31: "automatic_plus",
    37: "outerwear",
    39: "pillows",
    45: "cool_air",  # washer-dryer
    46: "warm_air",  # washer-dryer
    48: "rinse_out_lint",  # washer-dryer
    50: "dark_garments",
    52: "separate_rinse_starch",
    53: "first_wash",
    69: "cottons_hygiene",
    75: "steam_care",  # washer-dryer
    76: "freshen_up",  # washer-dryer
    77: "trainers",
    91: "clean_machine",
    95: "down_duvets",
    122: "express_20",
    123: "denim",
    129: "down_filled_items",
    133: "cottons_eco",
    146: "quick_power_wash",
    190: "eco_40_60",
}

DISHWASHER_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Sometimes returned by the API when the machine is switched off entirely, in conjunection with program phase 65535.
    0: "no_program",  # Returned by the API when the machine is switched off entirely.
    1: "intensive",
    2: "maintenance",
    3: "eco",
    6: "automatic",
    7: "automatic",
    9: "solar_save",
    10: "gentle",
    11: "extra_quiet",
    12: "hygiene",
    13: "quick_power_wash",
    14: "pasta_paela",
    17: "tall_items",
    19: "glasses_warm",
    26: "intensive",
    27: "maintenance",  # or maintenance_program?
    28: "eco",
    30: "normal",
    31: "automatic",
    32: "automatic",  # sources disagree on ID
    34: "solar_save",
    35: "gentle",
    36: "extra_quiet",
    37: "hygiene",
    38: "quick_power_wash",
    42: "tall_items",
    44: "power_wash",
}
TUMBLE_DRYER_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Extrapolated from other device types.
    0: "no_program",  # Extrapolated from other device types
    2: "cottons",
    3: "minimum_iron",
    4: "woollens_handcare",
    5: "delicates",
    6: "warm_air",
    8: "express",
    10: "automatic_plus",
    20: "cottons",
    23: "cottons_hygiene",
    30: "minimum_iron",
    31: "bed_linen",
    40: "woollens_handcare",
    50: "delicates",
    60: "warm_air",
    66: "eco",
    70: "cool_air",
    80: "express",
    90: "cottons",
    100: "gentle_smoothing",
    120: "proofing",
    130: "denim",
    131: "gentle_denim",
    150: "sportswear",
    160: "outerwear",
    170: "silks_handcare",
    190: "standard_pillows",
    220: "basket_program",
    240: "smoothing",
    99001: "steam_smoothing",
    99002: "bed_linen",
    99003: "cottons_eco",
    99004: "shirts",
    99005: "large_pillows",
}

OVEN_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Extrapolated from other device types.
    0: "no_program",  # Extrapolated from other device types
    1: "defrost",
    6: "eco_fan_heat",
    7: "auto_roast",
    10: "full_grill",
    11: "economy_grill",
    13: "fan_plus",
    14: "intensive_bake",
    19: "microwave",
    24: "conventional_heat",
    25: "top_heat",
    29: "fan_grill",
    31: "bottom_heat",
    35: "moisture_plus_auto_roast",
    40: "moisture_plus_fan_plus",
    48: "moisture_plus_auto_roast",
    49: "moisture_plus_fan_plus",
    50: "moisture_plus_intensive_bake",
    51: "moisture_plus_conventional_heat",
    74: "moisture_plus_intensive_bake",
    76: "moisture_plus_conventional_heat",
    323: "pyrolytic",
    326: "descale",
    335: "shabbat_program",
    336: "yom_tov",
    356: "defrost",
    357: "drying",
    358: "heat_crockery",
    360: "low_temperature_cooking",
    361: "steam_cooking",
    362: "keeping_warm",
    512: "1_tray",
    513: "2_trays",
    529: "baking_tray",
    554: "baiser_one_large",
    555: "baiser_several_small",
    556: "lemon_meringue_pie",
    557: "viennese_apple_strudel",
    621: "prove_15_min",
    622: "prove_30_min",
    623: "prove_45_min",
    99001: "steam_bake",
    17003: "no_program",
}
DISH_WARMER_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",
    0: "no_program",
    1: "warm_cups_glasses",
    2: "warm_dishes_plates",
    3: "keep_warm",
    4: "slow_roasting",
}
ROBOT_VACUUM_CLEANER_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Extrapolated from other device types
    0: "no_program",  # Extrapolated from other device types
    1: "auto",
    2: "spot",
    3: "turbo",
    4: "silent",
}
COFFEE_SYSTEM_PROGRAM_ID: dict[int, str] = {
    -1: "no_program",  # Extrapolated from other device types
    0: "no_program",  # Extrapolated from other device types
    16016: "appliance_settings",  # display brightness
    16018: "appliance_settings",  # volume
    16019: "appliance_settings",  # buttons volume
    16020: "appliance_settings",  # child lock
    16021: "appliance_settings",  # water hardness
    16027: "appliance_settings",  # welcome sound
    16033: "appliance_settings",  # connection status
    16035: "appliance_settings",  # remote control
    16037: "appliance_settings",  # remote update
    17004: "check_appliance",
    # profile 1
    24000: "ristretto",
    24001: "espresso",
    24002: "coffee",
    24003: "long_coffee",
    24004: "cappuccino",
    24005: "cappuccino_italiano",
    24006: "latte_macchiato",
    24007: "espresso_macchiato",
    24008: "cafe_au_lait",
    24009: "caffe_latte",
    24012: "flat_white",
    24013: "very_hot_water",
    24014: "hot_water",
    24015: "hot_milk",
    24016: "milk_foam",
    24017: "black_tea",
    24018: "herbal_tea",
    24019: "fruit_tea",
    24020: "green_tea",
    24021: "white_tea",
    24022: "japanese_tea",
    # profile 2
    24032: "ristretto",
    24033: "espresso",
    24034: "coffee",
    24035: "long_coffee",
    24036: "cappuccino",
    24037: "cappuccino_italiano",
    24038: "latte_macchiato",
    24039: "espresso_macchiato",
    24040: "cafe_au_lait",
    24041: "caffe_latte",
    24044: "flat_white",
    24045: "very_hot_water",
    24046: "hot_water",
    24047: "hot_milk",
    24048: "milk_foam",
    24049: "black_tea",
    24050: "herbal_tea",
    24051: "fruit_tea",
    24052: "green_tea",
    24053: "white_tea",
    24054: "japanese_tea",
    # profile 3
    24064: "ristretto",
    24065: "espresso",
    24066: "coffee",
    24067: "long_coffee",
    24068: "cappuccino",
    24069: "cappuccino_italiano",
    24070: "latte_macchiato",
    24071: "espresso_macchiato",
    24072: "cafe_au_lait",
    24073: "caffe_latte",
    24076: "flat_white",
    24077: "very_hot_water",
    24078: "hot_water",
    24079: "hot_milk",
    24080: "milk_foam",
    24081: "black_tea",
    24082: "herbal_tea",
    24083: "fruit_tea",
    24084: "green_tea",
    24085: "white_tea",
    24086: "japanese_tea",
    # profile 4
    24096: "ristretto",
    24097: "espresso",
    24098: "coffee",
    24099: "long_coffee",
    24100: "cappuccino",
    24101: "cappuccino_italiano",
    24102: "latte_macchiato",
    24103: "espresso_macchiato",
    24104: "cafe_au_lait",
    24105: "caffe_latte",
    24108: "flat_white",
    24109: "very_hot_water",
    24110: "hot_water",
    24111: "hot_milk",
    24112: "milk_foam",
    24113: "black_tea",
    24114: "herbal_tea",
    24115: "fruit_tea",
    24116: "green_tea",
    24117: "white_tea",
    24118: "japanese_tea",
    # profile 5
    24128: "ristretto",
    24129: "espresso",
    24130: "coffee",
    24131: "long_coffee",
    24132: "cappuccino",
    24133: "cappuccino_italiano",
    24134: "latte_macchiato",
    24135: "espresso_macchiato",
    24136: "cafe_au_lait",
    24137: "caffe_latte",
    24140: "flat_white",
    24141: "very_hot_water",
    24142: "hot_water",
    24143: "hot_milk",
    24144: "milk_foam",
    24145: "black_tea",
    24146: "herbal_tea",
    24147: "fruit_tea",
    24148: "green_tea",
    24149: "white_tea",
    24150: "japanese_tea",
    # special programs
    24400: "coffee_pot",
    24407: "barista_assistant",
    # machine settings menu
    24500: "appliance_settings",  # total dispensed
    24502: "appliance_settings",  # lights appliance on
    24503: "appliance_settings",  # lights appliance off
    24504: "appliance_settings",  # turn off lights after
    24506: "appliance_settings",  # altitude
    24513: "appliance_settings",  # performance mode
    24516: "appliance_settings",  # turn off after
    24537: "appliance_settings",  # advanced mode
    24542: "appliance_settings",  # tea timer
    24549: "appliance_settings",  # total coffee dispensed
    24550: "appliance_settings",  # total tea dispensed
    24551: "appliance_settings",  # total ristretto
    24552: "appliance_settings",  # total cappuccino
    24553: "appliance_settings",  # total espresso
    24554: "appliance_settings",  # total coffee
    24555: "appliance_settings",  # total long coffee
    24556: "appliance_settings",  # total italian cappuccino
    24557: "appliance_settings",  # total latte macchiato
    24558: "appliance_settings",  # total caffe latte
    24560: "appliance_settings",  # total espresso macchiato
    24562: "appliance_settings",  # total flat white
    24563: "appliance_settings",  # total coffee with milk
    24564: "appliance_settings",  # total black tea
    24565: "appliance_settings",  # total herbal tea
    24566: "appliance_settings",  # total fruit tea
    24567: "appliance_settings",  # total green tea
    24568: "appliance_settings",  # total white tea
    24569: "appliance_settings",  # total japanese tea
    24571: "appliance_settings",  # total milk foam
    24572: "appliance_settings",  # total hot milk
    24573: "appliance_settings",  # total hot water
    24574: "appliance_settings",  # total very hot water
    24575: "appliance_settings",  # counter to descaling
    24576: "appliance_settings",  # counter to brewing unit degreasing
    # maintenance
    24750: "appliance_rinse",
    24751: "descaling",
    24753: "brewing_unit_degrease",
    24754: "milk_pipework_rinse",
    24759: "appliance_rinse",
    24773: "appliance_rinse",
    24787: "appliance_rinse",
    24788: "appliance_rinse",
    24789: "milk_pipework_clean",
    # profiles settings menu
    24800: "appliance_settings",  # add profile
    24801: "appliance_settings",  # ask profile settings
    24813: "appliance_settings",  # modify profile name
}

STEAM_OVEN_MICRO_PROGRAM_ID: dict[int, str] = {
    8: "steam_cooking",
    19: "microwave",
    53: "popcorn",
    54: "quick_mw",
    72: "sous_vide",
    75: "eco_steam_cooking",
    77: "rapid_steam_cooking",
    326: "descale",
    330: "menu_cooking",
    2018: "reheating_with_steam",
    2019: "defrosting_with_steam",
    2020: "blanching",
    2021: "bottling",
    2022: "sterilize_crockery",
    2023: "prove_dough",
    2027: "soak",
    2029: "reheating_with_microwave",
    2030: "defrosting_with_microwave",
    2031: "artichokes_small",
    2032: "artichokes_medium",
    2033: "artichokes_large",
    2034: "eggplant_sliced",
    2035: "eggplant_diced",
    2036: "cauliflower_whole_small",
    2039: "cauliflower_whole_medium",
    2042: "cauliflower_whole_large",
    2046: "cauliflower_florets_small",
    2048: "cauliflower_florets_medium",
    2049: "cauliflower_florets_large",
    2051: "green_beans_whole",
    2052: "green_beans_cut",
    2053: "yellow_beans_whole",
    2054: "yellow_beans_cut",
    2055: "broad_beans",
    2056: "common_beans",
    2057: "runner_beans_whole",
    2058: "runner_beans_pieces",
    2059: "runner_beans_sliced",
    2060: "broccoli_whole_small",
    2061: "broccoli_whole_medium",
    2062: "broccoli_whole_large",
    2064: "broccoli_florets_small",
    2066: "broccoli_florets_medium",
    2068: "broccoli_florets_large",
    2069: "endive_halved",
    2070: "endive_quartered",
    2071: "endive_strips",
    2072: "chinese_cabbage_cut",
    2073: "peas",
    2074: "fennel_halved",
    2075: "fennel_quartered",
    2076: "fennel_strips",
    2077: "kale_cut",
    2080: "potatoes_in_the_skin_waxy_small_steam_cooking",
    2081: "potatoes_in_the_skin_waxy_small_rapid_steam_cooking",
    2083: "potatoes_in_the_skin_waxy_medium_steam_cooking",
    2084: "potatoes_in_the_skin_waxy_medium_rapid_steam_cooking",
    2086: "potatoes_in_the_skin_waxy_large_steam_cooking",
    2087: "potatoes_in_the_skin_waxy_large_rapid_steam_cooking",
    2088: "potatoes_in_the_skin_floury_small",
    2091: "potatoes_in_the_skin_floury_medium",
    2094: "potatoes_in_the_skin_floury_large",
    2097: "potatoes_in_the_skin_mainly_waxy_small",
    2100: "potatoes_in_the_skin_mainly_waxy_medium",
    2103: "potatoes_in_the_skin_mainly_waxy_large",
    2106: "potatoes_waxy_whole_small",
    2109: "potatoes_waxy_whole_medium",
    2112: "potatoes_waxy_whole_large",
    2115: "potatoes_waxy_halved",
    2116: "potatoes_waxy_quartered",
    2117: "potatoes_waxy_diced",
    2118: "potatoes_mainly_waxy_small",
    2119: "potatoes_mainly_waxy_medium",
    2120: "potatoes_mainly_waxy_large",
    2121: "potatoes_mainly_waxy_halved",
    2122: "potatoes_mainly_waxy_quartered",
    2123: "potatoes_mainly_waxy_diced",
    2124: "potatoes_floury_whole_small",
    2125: "potatoes_floury_whole_medium",
    2126: "potatoes_floury_whole_large",
    2127: "potatoes_floury_halved",
    2128: "potatoes_floury_quartered",
    2129: "potatoes_floury_diced",
    2130: "german_turnip_sliced",
    2131: "german_turnip_cut_into_batons",
    2132: "german_turnip_diced",
    2133: "pumpkin_diced",
    2134: "corn_on_the_cob",
    2135: "mangel_cut",
    2136: "bunched_carrots_whole_small",
    2137: "bunched_carrots_whole_medium",
    2138: "bunched_carrots_whole_large",
    2139: "bunched_carrots_halved",
    2140: "bunched_carrots_quartered",
    2141: "bunched_carrots_diced",
    2142: "bunched_carrots_cut_into_batons",
    2143: "bunched_carrots_sliced",
    2144: "parisian_carrots_small",
    2145: "parisian_carrots_medium",
    2146: "parisian_carrots_large",
    2147: "carrots_whole_small",
    2148: "carrots_whole_medium",
    2149: "carrots_whole_large",
    2150: "carrots_halved",
    2151: "carrots_quartered",
    2152: "carrots_diced",
    2153: "carrots_cut_into_batons",
    2155: "carrots_sliced",
    2156: "pepper_halved",
    2157: "pepper_quartered",
    2158: "pepper_strips",
    2159: "pepper_diced",
    2160: "parsnip_sliced",
    2161: "parsnip_diced",
    2162: "parsnip_cut_into_batons",
    2163: "parsley_root_sliced",
    2164: "parsley_root_diced",
    2165: "parsley_root_cut_into_batons",
    2166: "leek_pieces",
    2167: "leek_rings",
    2168: "romanesco_whole_small",
    2169: "romanesco_whole_medium",
    2170: "romanesco_whole_large",
    2171: "romanesco_florets_small",
    2172: "romanesco_florets_medium",
    2173: "romanesco_florets_large",
    2175: "brussels_sprout",
    2176: "beetroot_whole_small",
    2177: "beetroot_whole_medium",
    2178: "beetroot_whole_large",
    2179: "red_cabbage_cut",
    2180: "black_salsify_thin",
    2181: "black_salsify_medium",
    2182: "black_salsify_thick",
    2183: "celery_pieces",
    2184: "celery_sliced",
    2185: "celeriac_sliced",
    2186: "celeriac_cut_into_batons",
    2187: "celeriac_diced",
    2188: "white_asparagus_thin",
    2189: "white_asparagus_medium",
    2190: "white_asparagus_thick",
    2192: "green_asparagus_thin",
    2194: "green_asparagus_medium",
    2196: "green_asparagus_thick",
    2197: "spinach",
    2198: "pointed_cabbage_cut",
    2199: "yam_halved",
    2200: "yam_quartered",
    2201: "yam_strips",
    2202: "swede_diced",
    2203: "swede_cut_into_batons",
    2204: "teltow_turnip_sliced",
    2205: "teltow_turnip_diced",
    2206: "jerusalem_artichoke_sliced",
    2207: "jerusalem_artichoke_diced",
    2208: "green_cabbage_cut",
    2209: "savoy_cabbage_cut",
    2210: "courgette_sliced",
    2211: "courgette_diced",
    2212: "snow_pea",
    2214: "perch_whole",
    2215: "perch_fillet_2_cm",
    2216: "perch_fillet_3_cm",
    2217: "gilt_head_bream_whole",
    2220: "gilt_head_bream_fillet",
    2221: "codfish_piece",
    2222: "codfish_fillet",
    2224: "trout",
    2225: "pike_fillet",
    2226: "pike_piece",
    2227: "halibut_fillet_2_cm",
    2230: "halibut_fillet_3_cm",
    2231: "codfish_fillet",
    2232: "codfish_piece",
    2233: "carp",
    2234: "salmon_fillet_2_cm",
    2235: "salmon_fillet_3_cm",
    2238: "salmon_steak_2_cm",
    2239: "salmon_steak_3_cm",
    2240: "salmon_piece",
    2241: "salmon_trout",
    2244: "iridescent_shark_fillet",
    2245: "red_snapper_fillet_2_cm",
    2248: "red_snapper_fillet_3_cm",
    2249: "redfish_fillet_2_cm",
    2250: "redfish_fillet_3_cm",
    2251: "redfish_piece",
    2252: "char",
    2253: "plaice_whole_2_cm",
    2254: "plaice_whole_3_cm",
    2255: "plaice_whole_4_cm",
    2256: "plaice_fillet_1_cm",
    2259: "plaice_fillet_2_cm",
    2260: "coalfish_fillet_2_cm",
    2261: "coalfish_fillet_3_cm",
    2262: "coalfish_piece",
    2263: "sea_devil_fillet_3_cm",
    2266: "sea_devil_fillet_4_cm",
    2267: "common_sole_fillet_1_cm",
    2270: "common_sole_fillet_2_cm",
    2271: "atlantic_catfish_fillet_1_cm",
    2272: "atlantic_catfish_fillet_2_cm",
    2273: "turbot_fillet_2_cm",
    2276: "turbot_fillet_3_cm",
    2277: "tuna_steak",
    2278: "tuna_fillet_2_cm",
    2279: "tuna_fillet_3_cm",
    2280: "tilapia_fillet_1_cm",
    2281: "tilapia_fillet_2_cm",
    2282: "nile_perch_fillet_2_cm",
    2283: "nile_perch_fillet_3_cm",
    2285: "zander_fillet",
    2288: "soup_hen",
    2291: "poularde_whole",
    2292: "poularde_breast",
    2294: "turkey_breast",
    2302: "chicken_tikka_masala_with_rice",
    2312: "veal_fillet_whole",
    2313: "veal_fillet_medaillons_1_cm",
    2315: "veal_fillet_medaillons_2_cm",
    2317: "veal_fillet_medaillons_3_cm",
    2324: "goulash_soup",
    2327: "dutch_hash",
    2328: "stuffed_cabbage",
    2330: "beef_tenderloin",
    2333: "beef_tenderloin_medaillons_1_cm_steam_cooking",
    2334: "beef_tenderloin_medaillons_2_cm_steam_cooking",
    2335: "beef_tenderloin_medaillons_3_cm_steam_cooking",
    2339: "silverside_5_cm",
    2342: "silverside_7_5_cm",
    2345: "silverside_10_cm",
    2348: "meat_for_soup_back_or_top_rib",
    2349: "meat_for_soup_leg_steak",
    2350: "meat_for_soup_brisket",
    2353: "viennese_silverside",
    2354: "whole_ham_steam_cooking",
    2355: "whole_ham_reheating",
    2359: "kasseler_piece",
    2361: "kasseler_slice",
    2363: "knuckle_of_pork_fresh",
    2364: "knuckle_of_pork_cured",
    2367: "pork_tenderloin_medaillons_3_cm",
    2368: "pork_tenderloin_medaillons_4_cm",
    2369: "pork_tenderloin_medaillons_5_cm",
    2429: "pumpkin_soup",
    2430: "meat_with_rice",
    2431: "beef_casserole",
    2450: "risotto",
    2451: "risotto",
    2453: "rice_pudding_steam_cooking",
    2454: "rice_pudding_rapid_steam_cooking",
    2461: "amaranth",
    2462: "bulgur",
    2463: "spelt_whole",
    2464: "spelt_cracked",
    2465: "green_spelt_whole",
    2466: "green_spelt_cracked",
    2467: "oats_whole",
    2468: "oats_cracked",
    2469: "millet",
    2470: "quinoa",
    2471: "polenta_swiss_style_fine_polenta",
    2472: "polenta_swiss_style_medium_polenta",
    2473: "polenta_swiss_style_coarse_polenta",
    2474: "polenta",
    2475: "rye_whole",
    2476: "rye_cracked",
    2477: "wheat_whole",
    2478: "wheat_cracked",
    2480: "gnocchi_fresh",
    2481: "yeast_dumplings_fresh",
    2482: "potato_dumplings_raw_boil_in_bag",
    2483: "potato_dumplings_raw_deep_frozen",
    2484: "potato_dumplings_half_half_boil_in_bag",
    2485: "potato_dumplings_half_half_deep_frozen",
    2486: "bread_dumplings_boil_in_the_bag",
    2487: "bread_dumplings_fresh",
    2488: "ravioli_fresh",
    2489: "spaetzle_fresh",
    2490: "tagliatelli_fresh",
    2491: "schupfnudeln_potato_noodels",
    2492: "tortellini_fresh",
    2493: "red_lentils",
    2494: "brown_lentils",
    2495: "beluga_lentils",
    2496: "green_split_peas",
    2497: "yellow_split_peas",
    2498: "chick_peas",
    2499: "white_beans",
    2500: "pinto_beans",
    2501: "red_beans",
    2502: "black_beans",
    2503: "hens_eggs_size_s_soft",
    2504: "hens_eggs_size_s_medium",
    2505: "hens_eggs_size_s_hard",
    2506: "hens_eggs_size_m_soft",
    2507: "hens_eggs_size_m_medium",
    2508: "hens_eggs_size_m_hard",
    2509: "hens_eggs_size_l_soft",
    2510: "hens_eggs_size_l_medium",
    2511: "hens_eggs_size_l_hard",
    2512: "hens_eggs_size_xl_soft",
    2513: "hens_eggs_size_xl_medium",
    2514: "hens_eggs_size_xl_hard",
    2515: "swiss_toffee_cream_100_ml",
    2516: "swiss_toffee_cream_150_ml",
    2518: "toffee_date_dessert_several_small",
    2520: "cheesecake_several_small",
    2521: "cheesecake_one_large",
    2522: "christmas_pudding_cooking",
    2523: "christmas_pudding_heating",
    2524: "treacle_sponge_pudding_several_small",
    2525: "treacle_sponge_pudding_one_large",
    2526: "sweet_cheese_dumplings",
    2527: "apples_whole",
    2528: "apples_halved",
    2529: "apples_quartered",
    2530: "apples_sliced",
    2531: "apples_diced",
    2532: "apricots_halved_steam_cooking",
    2533: "apricots_halved_skinning",
    2534: "apricots_quartered",
    2535: "apricots_wedges",
    2536: "pears_halved",
    2537: "pears_quartered",
    2538: "pears_wedges",
    2539: "sweet_cherries",
    2540: "sour_cherries",
    2541: "pears_to_cook_small_whole",
    2542: "pears_to_cook_small_halved",
    2543: "pears_to_cook_small_quartered",
    2544: "pears_to_cook_medium_whole",
    2545: "pears_to_cook_medium_halved",
    2546: "pears_to_cook_medium_quartered",
    2547: "pears_to_cook_large_whole",
    2548: "pears_to_cook_large_halved",
    2549: "pears_to_cook_large_quartered",
    2550: "mirabelles",
    2551: "nectarines_peaches_halved_steam_cooking",
    2552: "nectarines_peaches_halved_skinning",
    2553: "nectarines_peaches_quartered",
    2554: "nectarines_peaches_wedges",
    2555: "plums_whole",
    2556: "plums_halved",
    2557: "cranberries",
    2558: "quinces_diced",
    2559: "greenage_plums",
    2560: "rhubarb_chunks",
    2561: "gooseberries",
    2562: "mushrooms_whole",
    2563: "mushrooms_halved",
    2564: "mushrooms_sliced",
    2565: "mushrooms_quartered",
    2566: "mushrooms_diced",
    2567: "cep",
    2568: "chanterelle",
    2569: "oyster_mushroom_whole",
    2570: "oyster_mushroom_strips",
    2571: "oyster_mushroom_diced",
    2572: "saucisson",
    2573: "bruehwurst_sausages",
    2574: "bologna_sausage",
    2575: "veal_sausages",
    2577: "crevettes",
    2579: "prawns",
    2581: "king_prawns",
    2583: "small_shrimps",
    2585: "large_shrimps",
    2587: "mussels",
    2589: "scallops",
    2591: "venus_clams",
    2592: "goose_barnacles",
    2593: "cockles",
    2594: "razor_clams_small",
    2595: "razor_clams_medium",
    2596: "razor_clams_large",
    2597: "mussels_in_sauce",
    2598: "bottling_soft",
    2599: "bottling_medium",
    2600: "bottling_hard",
    2601: "melt_chocolate",
    2602: "dissolve_gelatine",
    2603: "sweat_onions",
    2604: "cook_bacon",
    2605: "heating_damp_flannels",
    2606: "decrystallise_honey",
    2607: "make_yoghurt",
    2687: "toffee_date_dessert_one_large",
    2694: "beef_tenderloin_medaillons_1_cm_low_temperature_cooking",
    2695: "beef_tenderloin_medaillons_2_cm_low_temperature_cooking",
    2696: "beef_tenderloin_medaillons_3_cm_low_temperature_cooking",
    3373: "wild_rice",
    3376: "wholegrain_rice",
    3380: "parboiled_rice_steam_cooking",
    3381: "parboiled_rice_rapid_steam_cooking",
    3383: "basmati_rice_steam_cooking",
    3384: "basmati_rice_rapid_steam_cooking",
    3386: "jasmine_rice_steam_cooking",
    3387: "jasmine_rice_rapid_steam_cooking",
    3389: "huanghuanian_steam_cooking",
    3390: "huanghuanian_rapid_steam_cooking",
    3392: "simiao_steam_cooking",
    3393: "simiao_rapid_steam_cooking",
    3395: "long_grain_rice_general_steam_cooking",
    3396: "long_grain_rice_general_rapid_steam_cooking",
    3398: "chongming_steam_cooking",
    3399: "chongming_rapid_steam_cooking",
    3401: "wuchang_steam_cooking",
    3402: "wuchang_rapid_steam_cooking",
    3404: "uonumma_koshihikari_steam_cooking",
    3405: "uonumma_koshihikari_rapid_steam_cooking",
    3407: "sheyang_steam_cooking",
    3408: "sheyang_rapid_steam_cooking",
    3410: "round_grain_rice_general_steam_cooking",
    3411: "round_grain_rice_general_rapid_steam_cooking",
}

STATE_PROGRAM_ID: dict[int, dict[int, str]] = {
    MieleAppliance.WASHING_MACHINE: WASHING_MACHINE_PROGRAM_ID,
    MieleAppliance.TUMBLE_DRYER: TUMBLE_DRYER_PROGRAM_ID,
    MieleAppliance.DISHWASHER: DISHWASHER_PROGRAM_ID,
    MieleAppliance.DISH_WARMER: DISH_WARMER_PROGRAM_ID,
    MieleAppliance.OVEN: OVEN_PROGRAM_ID,
    MieleAppliance.OVEN_MICROWAVE: OVEN_PROGRAM_ID,
    MieleAppliance.STEAM_OVEN_MK2: OVEN_PROGRAM_ID,
    MieleAppliance.STEAM_OVEN: OVEN_PROGRAM_ID,
    MieleAppliance.STEAM_OVEN_COMBI: OVEN_PROGRAM_ID,
    MieleAppliance.STEAM_OVEN_MICRO: STEAM_OVEN_MICRO_PROGRAM_ID,
    MieleAppliance.WASHER_DRYER: WASHING_MACHINE_PROGRAM_ID,
    MieleAppliance.ROBOT_VACUUM_CLEANER: ROBOT_VACUUM_CLEANER_PROGRAM_ID,
    MieleAppliance.COFFEE_SYSTEM: COFFEE_SYSTEM_PROGRAM_ID,
}

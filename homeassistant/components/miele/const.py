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


class ProgramPhaseWashingMachine(MieleEnum, missing_to_none=True):
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


class ProgramPhaseTumbleDryer(MieleEnum, missing_to_none=True):
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


class ProgramPhaseWasherDryer(MieleEnum, missing_to_none=True):
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
    finished = 268, 522
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


class ProgramPhaseDishwasher(MieleEnum, missing_to_none=True):
    """Program phase codes for dishwashers."""

    not_running = 0, 1792, 65535
    reactivating = 1793
    pre_dishwash = 1794, 1801
    main_dishwash = 1795
    rinse = 1796
    interim_rinse = 1797
    final_rinse = 1798
    drying = 1799
    finished = 1800


class ProgramPhaseOven(MieleEnum, missing_to_none=True):
    """Program phase codes for ovens."""

    not_running = 0, 65535
    heating_up = 3073
    process_running = 3074
    process_finished = 3078
    energy_save = 3084


class ProgramPhaseWarmingDrawer(MieleEnum, missing_to_none=True):
    """Program phase codes for warming drawers."""

    not_running = 0, 65535
    heating_up = 3073
    door_open = 3075
    keeping_warm = 3094
    cooling_down = 3088
    missing2none = -9999


class ProgramPhaseMicrowave(MieleEnum, missing_to_none=True):
    """Program phase for microwave units."""

    not_running = 0, 65535
    heating = 3329
    process_running = 3330
    process_finished = 3334
    energy_save = 3340


class ProgramPhaseCoffeeSystem(MieleEnum, missing_to_none=True):
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
    missing2none = -9999


class ProgramPhaseRobotVacuumCleaner(MieleEnum, missing_to_none=True):
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
    missing2none = -9999


class ProgramPhaseMicrowaveOvenCombo(MieleEnum, missing_to_none=True):
    """Program phase codes for microwave oven combo."""

    not_running = 0, 65535
    steam_reduction = 3863
    process_running = 7938
    waiting_for_start = 7939
    heating_up_phase = 7940
    process_finished = 7942
    missing2none = -9999


class ProgramPhaseSteamOven(MieleEnum, missing_to_none=True):
    """Program phase codes for steam ovens."""

    not_running = 0, 65535
    steam_reduction = 3863
    process_running = 7938
    waiting_for_start = 7939
    heating_up_phase = 7940
    process_finished = 7942


class ProgramPhaseSteamOvenCombi(MieleEnum, missing_to_none=True):
    """Program phase codes for steam oven combi."""

    not_running = 0, 65535
    heating_up = 3073
    process_running = 3074, 7938
    process_finished = 3078, 7942
    energy_save = 3084

    steam_reduction = 3863
    waiting_for_start = 7939
    heating_up_phase = 7940


class ProgramPhaseSteamOvenMicro(MieleEnum, missing_to_none=True):
    """Program phase codes for steam oven micro."""

    not_running = 0, 65535

    heating = 3329
    process_running = 3330, 7938, 7942
    process_finished = 3334
    energy_save = 3340

    steam_reduction = 3863
    waiting_for_start = 7939
    heating_up_phase = 7940


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
    MieleAppliance.STEAM_OVEN: ProgramPhaseSteamOven,
    MieleAppliance.STEAM_OVEN_COMBI: ProgramPhaseSteamOvenCombi,
    MieleAppliance.STEAM_OVEN_MK2: ProgramPhaseSteamOvenCombi,
    MieleAppliance.STEAM_OVEN_MICRO: ProgramPhaseSteamOvenMicro,
    MieleAppliance.DIALOG_OVEN: ProgramPhaseOven,
    MieleAppliance.MICROWAVE: ProgramPhaseMicrowave,
    MieleAppliance.COFFEE_SYSTEM: ProgramPhaseCoffeeSystem,
    MieleAppliance.ROBOT_VACUUM_CLEANER: ProgramPhaseRobotVacuumCleaner,
    MieleAppliance.DISH_WARMER: ProgramPhaseWarmingDrawer,
}


class StateProgramType(MieleEnum, missing_to_none=True):
    """Defines program types."""

    normal_operation_mode = 0
    own_program = 1
    automatic_program = 2
    cleaning_care_program = 3
    maintenance_program = 4


class StateDryingStep(MieleEnum, missing_to_none=True):
    """Defines drying steps."""

    extra_dry = 0
    normal_plus = 1
    normal = 2
    slightly_dry = 3
    hand_iron_1 = 4
    hand_iron_2 = 5
    machine_iron = 6
    smoothing = 7


class WashingMachineProgramId(MieleEnum):
    """Program Id codes for washing machines."""

    no_program = 0, -1
    cottons = 1
    minimum_iron = 3
    delicates = 4
    woollens = 8
    silks = 9
    starch = 17
    rinse = 18
    drain_spin = 21
    curtains = 22
    shirts = 23
    denim = 24, 123
    proofing = 27
    sportswear = 29
    automatic_plus = 31
    outerwear = 37
    pillows = 39
    cool_air = 45  # washer-dryer
    warm_air = 46  # washer-dryer
    rinse_out_lint = 48  # washer-dryer
    dark_garments = 50
    separate_rinse_starch = 52
    first_wash = 53
    cottons_hygiene = 69
    steam_care = 75  # washer-dryer
    freshen_up = 76  # washer-dryer
    trainers = 77
    clean_machine = 91
    down_duvets = 95
    express_20 = 122
    down_filled_items = 129
    cottons_eco = 133
    quick_power_wash = 146
    eco_40_60 = 190
    missing2none = -9999


class DishWasherProgramId(MieleEnum):
    """Program Id codes for dishwashers."""

    no_program = 0, -1
    intensive = 1, 26
    maintenance = 2, 27
    eco = 3, 28
    automatic = 6, 7, 31, 32
    solar_save = 9, 34
    gentle = 10, 35
    extra_quiet = 11, 36
    hygiene = 12, 37
    quick_power_wash = 13, 38
    pasta_paela = 14
    tall_items = 17, 42
    glasses_warm = 19
    normal = 30
    power_wash = 44
    missing2none = -9999


class TumbleDryerProgramId(MieleEnum):
    """Program Id codes for tumble dryers."""

    no_program = 0, -1
    automatic_plus = 1, 10
    cottons = 2, 20, 90
    minimum_iron = 3, 30
    woollens_handcare = 4, 40
    delicates = 5, 50
    warm_air = 6, 60
    cool_air = 7, 70
    express = 8, 80
    cottons_eco = 9, 99003
    proofing = 12, 120
    denim = 13, 130
    shirts = 14, 99004
    sportswear = 15, 150
    outerwear = 16, 160
    silks_handcare = 17, 170
    standard_pillows = 19, 190
    basket_program = 22, 220
    cottons_hygiene = 23
    smoothing = 24, 240
    bed_linen = 31, 99002
    eco = 66
    gentle_smoothing = 100
    gentle_denim = 131
    steam_smoothing = 99001
    large_pillows = 99005
    missing2none = -9999


class OvenProgramId(MieleEnum):
    """Program Id codes for ovens."""

    no_program = 0, -1, 17003
    defrost = 1, 356
    eco_fan_heat = 6
    auto_roast = 7
    full_grill = 10
    economy_grill = 11
    fan_plus = 13
    intensive_bake = 14
    microwave = 19
    conventional_heat = 24
    top_heat = 25
    fan_grill = 29
    bottom_heat = 31
    moisture_plus_auto_roast = 35, 48
    moisture_plus_fan_plus = 40, 49
    moisture_plus_intensive_bake = 50, 74
    moisture_plus_conventional_heat = 51, 76
    pyrolytic = 323
    descale = 326
    shabbat_program = 335
    yom_tov = 336
    drying = 357
    heat_crockery = 358
    low_temperature_cooking = 360
    steam_cooking = 361
    keeping_warm = 362
    one_tray = 512
    two_trays = 513
    baking_tray = 529
    baiser_one_large = 554
    baiser_several_small = 555
    lemon_meringue_pie = 556
    viennese_apple_strudel = 557
    prove_15_min = 621
    prove_30_min = 622
    prove_45_min = 623
    steam_bake = 99001
    missing2none = -9999


class DishWarmerProgramId(MieleEnum):
    """Program Id codes for dish warmers."""

    no_program = 0, -1
    warm_cups_glasses = 1
    warm_dishes_plates = 2
    keep_warm = 3
    slow_roasting = 4
    missing2none = -9999


class RobotVacuumCleanerProgramId(MieleEnum):
    """Program Id codes for robot vacuum cleaners."""

    no_program = 0, -1
    auto = 1
    spot = 2
    turbo = 3
    silent = 4
    missing2none = -9999


class CoffeeSystemProgramId(MieleEnum):
    """Program Id codes for coffee systems."""

    no_program = 0, -1

    check_appliance = 17004
    # DISHWASHER_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",  # Sometimes returned by the API when the machine is switched off entirely, in conjunection with program phase 65535.
    #     0: "no_program",  # Returned by the API when the machine is switched off entirely.
    #     1: "intensive",
    #     2: "maintenance",
    #     3: "eco",
    #     6: "automatic",
    #     7: "automatic",
    #     9: "solar_save",
    #     10: "gentle",
    #     11: "extra_quiet",
    #     12: "hygiene",
    #     13: "quick_power_wash",
    #     14: "pasta_paela",
    #     17: "tall_items",
    #     19: "glasses_warm",
    #     26: "intensive",
    #     27: "maintenance",  # or maintenance_program?
    #     28: "eco",
    #     30: "normal",
    #     31: "automatic",
    #     32: "automatic",  # sources disagree on ID
    #     34: "solar_save",
    #     35: "gentle",
    #     36: "extra_quiet",
    #     37: "hygiene",
    #     38: "quick_power_wash",
    #     42: "tall_items",
    #     44: "power_wash",
    #     200: "eco",
    #     202: "automatic",
    #     203: "comfort_wash",
    #     204: "power_wash",
    #     205: "intensive",
    #     207: "extra_quiet",
    #     209: "comfort_wash_plus",
    #     210: "gentle",
    #     214: "maintenance",
    #     215: "rinse_salt",
    # }
    # TUMBLE_DRYER_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",  # Extrapolated from other device types.
    #     0: "no_program",  # Extrapolated from other device types
    #     1: "automatic_plus",
    #     2: "cottons",
    #     3: "minimum_iron",
    #     4: "woollens_handcare",
    #     5: "delicates",
    #     6: "warm_air",
    #     7: "cool_air",
    #     8: "express",
    #     9: "cottons_eco",
    #     10: "gentle_smoothing",
    #     12: "proofing",
    #     13: "denim",
    #     14: "shirts",
    #     15: "sportswear",
    #     16: "outerwear",
    #     17: "silks_handcare",
    #     19: "standard_pillows",
    #     20: "cottons",
    #     22: "basket_program",
    #     23: "cottons_hygiene",
    #     24: "steam_smoothing",
    #     30: "minimum_iron",
    #     31: "bed_linen",
    #     40: "woollens_handcare",
    #     50: "delicates",
    #     60: "warm_air",
    #     66: "eco",
    #     70: "cool_air",
    #     80: "express",
    #     90: "cottons",
    #     100: "gentle_smoothing",
    #     120: "proofing",
    #     130: "denim",
    #     131: "gentle_denim",
    #     150: "sportswear",
    #     160: "outerwear",
    #     170: "silks_handcare",
    #     190: "standard_pillows",
    #     220: "basket_program",
    #     240: "smoothing",
    #     99001: "steam_smoothing",
    #     99002: "bed_linen",
    #     99003: "cottons_eco",
    #     99004: "shirts",
    #     99005: "large_pillows",
    # }

    # OVEN_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",  # Extrapolated from other device types.
    #     0: "no_program",  # Extrapolated from other device types
    #     1: "defrost",
    #     6: "eco_fan_heat",
    #     7: "auto_roast",
    #     10: "full_grill",
    #     11: "economy_grill",
    #     13: "fan_plus",
    #     14: "intensive_bake",
    #     19: "microwave",
    #     24: "conventional_heat",
    #     25: "top_heat",
    #     29: "fan_grill",
    #     31: "bottom_heat",
    #     35: "moisture_plus_auto_roast",
    #     40: "moisture_plus_fan_plus",
    #     48: "moisture_plus_auto_roast",
    #     49: "moisture_plus_fan_plus",
    #     50: "moisture_plus_intensive_bake",
    #     51: "moisture_plus_conventional_heat",
    #     74: "moisture_plus_intensive_bake",
    #     76: "moisture_plus_conventional_heat",
    #     97: "custom_program_1",
    #     98: "custom_program_2",
    #     99: "custom_program_3",
    #     100: "custom_program_4",
    #     101: "custom_program_5",
    #     102: "custom_program_6",
    #     103: "custom_program_7",
    #     104: "custom_program_8",
    #     105: "custom_program_9",
    #     106: "custom_program_10",
    #     107: "custom_program_11",
    #     108: "custom_program_12",
    #     109: "custom_program_13",
    #     110: "custom_program_14",
    #     111: "custom_program_15",
    #     112: "custom_program_16",
    #     113: "custom_program_17",
    #     114: "custom_program_18",
    #     115: "custom_program_19",
    #     116: "custom_program_20",
    #     323: "pyrolytic",
    #     326: "descale",
    #     327: "evaporate_water",
    #     335: "shabbat_program",
    #     336: "yom_tov",
    #     356: "defrost",
    #     357: "drying",
    #     358: "heat_crockery",
    #     360: "low_temperature_cooking",
    #     361: "steam_cooking",
    #     362: "keeping_warm",
    #     364: "apple_sponge",
    #     365: "apple_pie",
    #     367: "sponge_base",
    #     368: "swiss_roll",
    #     369: "butter_cake",
    #     373: "marble_cake",
    #     374: "fruit_streusel_cake",
    #     375: "madeira_cake",
    #     378: "blueberry_muffins",
    #     379: "walnut_muffins",
    #     382: "baguettes",
    #     383: "flat_bread",
    #     384: "plaited_loaf",
    #     385: "seeded_loaf",
    #     386: "white_bread_baking_tin",
    #     387: "white_bread_on_tray",
    #     394: "duck",
    #     396: "chicken_whole",
    #     397: "chicken_thighs",
    #     401: "turkey_whole",
    #     402: "turkey_drumsticks",
    #     406: "veal_fillet_roast",
    #     407: "veal_fillet_low_temperature_cooking",
    #     408: "veal_knuckle",
    #     409: "saddle_of_veal_roast",
    #     410: "saddle_of_veal_low_temperature_cooking",
    #     411: "braised_veal",
    #     415: "leg_of_lamb",
    #     419: "saddle_of_lamb_roast",
    #     420: "saddle_of_lamb_low_temperature_cooking",
    #     422: "beef_fillet_roast",
    #     423: "beef_fillet_low_temperature_cooking",
    #     427: "braised_beef",
    #     428: "roast_beef_roast",
    #     429: "roast_beef_low_temperature_cooking",
    #     435: "pork_smoked_ribs_roast",
    #     436: "pork_smoked_ribs_low_temperature_cooking",
    #     443: "ham_roast",
    #     449: "pork_fillet_roast",
    #     450: "pork_fillet_low_temperature_cooking",
    #     454: "saddle_of_venison",
    #     455: "rabbit",
    #     456: "saddle_of_roebuck",
    #     461: "salmon_fillet",
    #     464: "potato_cheese_gratin",
    #     486: "trout",
    #     491: "carp",
    #     492: "salmon_trout",
    #     496: "springform_tin_15cm",
    #     497: "springform_tin_20cm",
    #     498: "springform_tin_25cm",
    #     499: "fruit_flan_puff_pastry",
    #     500: "fruit_flan_short_crust_pastry",
    #     501: "sachertorte",
    #     502: "chocolate_hazlenut_cake_one_large",
    #     503: "chocolate_hazlenut_cake_several_small",
    #     504: "stollen",
    #     505: "drop_cookies_1_tray",
    #     506: "drop_cookies_2_trays",
    #     507: "linzer_augen_1_tray",
    #     508: "linzer_augen_2_trays",
    #     509: "almond_macaroons_1_tray",
    #     510: "almond_macaroons_2_trays",
    #     512: "biscuits_short_crust_pastry_1_tray",
    #     513: "biscuits_short_crust_pastry_2_trays",
    #     514: "vanilla_biscuits_1_tray",
    #     515: "vanilla_biscuits_2_trays",
    #     516: "choux_buns",
    #     518: "spelt_bread",
    #     519: "walnut_bread",
    #     520: "mixed_rye_bread",
    #     522: "dark_mixed_grain_bread",
    #     525: "multigrain_rolls",
    #     526: "rye_rolls",
    #     527: "white_rolls",
    #     528: "tart_flambe",
    #     529: "pizza_yeast_dough_baking_tray",
    #     530: "pizza_yeast_dough_round_baking_tine",
    #     531: "pizza_oil_cheese_dough_baking_tray",
    #     532: "pizza_oil_cheese_dough_round_baking_tine",
    #     533: "quiche_lorraine",
    #     534: "savoury_flan_puff_pastry",
    #     535: "savoury_flan_short_crust_pastry",
    #     536: "osso_buco",
    #     539: "beef_hash",
    #     543: "pork_with_crackling",
    #     550: "potato_gratin",
    #     551: "cheese_souffle",
    #     554: "baiser_one_large",
    #     555: "baiser_several_small",
    #     556: "lemon_meringue_pie",
    #     557: "viennese_apple_strudel",
    #     621: "prove_15_min",
    #     622: "prove_30_min",
    #     623: "prove_45_min",
    #     624: "belgian_sponge_cake",
    #     625: "goose_unstuffed",
    #     634: "rack_of_lamb_with_vegetables",
    #     635: "yorkshire_pudding",
    #     636: "meat_loaf",
    #     695: "swiss_farmhouse_bread",
    #     696: "plaited_swiss_loaf",
    #     697: "tiger_bread",
    #     698: "ginger_loaf",
    #     699: "goose_stuffed",
    #     700: "beef_wellington",
    #     701: "pork_belly",
    #     702: "pikeperch_fillet_with_vegetables",
    #     99001: "steam_bake",
    #     17003: "no_program",
    # }
    # DISH_WARMER_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",
    #     0: "no_program",
    #     1: "warm_cups_glasses",
    #     2: "warm_dishes_plates",
    #     3: "keep_warm",
    #     4: "slow_roasting",
    # }
    # ROBOT_VACUUM_CLEANER_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",  # Extrapolated from other device types
    #     0: "no_program",  # Extrapolated from other device types
    #     1: "auto",
    #     2: "spot",
    #     3: "turbo",
    #     4: "silent",
    # }
    # COFFEE_SYSTEM_PROGRAM_ID: dict[int, str] = {
    #     -1: "no_program",  # Extrapolated from other device types
    #     0: "no_program",  # Extrapolated from other device types
    #     16016: "appliance_settings",  # display brightness
    #     16018: "appliance_settings",  # volume
    #     16019: "appliance_settings",  # buttons volume
    #     16020: "appliance_settings",  # child lock
    #     16021: "appliance_settings",  # water hardness
    #     16027: "appliance_settings",  # welcome sound
    #     16033: "appliance_settings",  # connection status
    #     16035: "appliance_settings",  # remote control
    #     16037: "appliance_settings",  # remote update
    #     17004: "check_appliance",
    # profile 1
    ristretto = 24000, 24032, 24064, 24096, 24128
    espresso = 24001, 24033, 24065, 24097, 24129
    coffee = 24002, 24034, 24066, 24098, 24130
    long_coffee = 24003, 24035, 24067, 24099, 24131
    cappuccino = 24004, 24036, 24068, 24100, 24132
    cappuccino_italiano = 24005, 24037, 24069, 24101, 24133
    latte_macchiato = 24006, 24038, 24070, 24102, 24134
    espresso_macchiato = 24007, 24039, 24071, 24135
    cafe_au_lait = 24008, 24040, 24072, 24104, 24136
    caffe_latte = 24009, 24041, 24073, 24105, 24137
    flat_white = 24012, 24044, 24076, 24108, 24140
    very_hot_water = 24013, 24045, 24077, 24109, 24141
    hot_water = 24014, 24046, 24078, 24110, 24142
    hot_milk = 24015, 24047, 24079, 24111, 24143
    milk_foam = 24016, 24048, 24080, 24112, 24144
    black_tea = 24017, 24049, 24081, 24113, 24145
    herbal_tea = 24018, 24050, 24082, 24114, 24146
    fruit_tea = 24019, 24051, 24083, 24115, 24147
    green_tea = 24020, 24052, 24084, 24116, 24148
    white_tea = 24021, 24053, 24085, 24117, 24149
    japanese_tea = 24022, 29054, 24086, 24118, 24150
    # special programs
    coffee_pot = 24400
    barista_assistant = 24407
    # machine settings menu
    appliance_settings = (
        16016,
        16018,
        16019,
        16020,
        16021,
        16027,
        16033,
        16035,
        16037,
        24500,
        24502,
        24503,
        24504,
        24506,
        24513,
        24516,
        24537,
        24542,
        24549,
        24550,
        24551,
        24552,
        24553,
        24554,
        24555,
        24556,
        24557,
        24558,
        24560,
        24562,
        24563,
        24564,
        24565,
        24566,
        24567,
        24568,
        24569,
        24571,
        24572,
        24573,
        24574,
        24575,
        24576,
        24800,
        24801,
        24813,
    )
    # display brightness
    # volume
    # buttons volume
    # child lock
    # water hardness
    # welcome sound
    # connection status
    # remote control
    # remote update
    # total dispensed
    # lights appliance on
    # lights appliance off
    # turn off lights after
    # altitude
    # performance mode
    # turn off after
    # advanced mode
    # tea timer
    # total coffee dispensed
    # total tea dispensed
    # total ristretto
    # total cappuccino
    # total espresso
    # total coffee
    # total long coffee
    # total italian cappuccino
    # total latte macchiato
    # total caffe latte
    # total espresso macchiato
    # total flat white
    # total coffee with milk
    # total black tea
    # total herbal tea
    # total fruit tea
    # total green tea
    # total white tea
    # total japanese tea
    # total milk foam
    # total hot milk
    # total hot water
    # total very hot water
    # counter to descaling
    # counter to brewing unit degreasing
    # maintenance
    # profiles settings menu
    # add profile
    # ask profile settings
    # modify profile name
    appliance_rinse = 24750, 24759, 24773, 24787, 24788
    descaling = 24751
    brewing_unit_degrease = 24753
    milk_pipework_rinse = 24754
    milk_pipework_clean = 24789
    missing2none = -9999


class SteamOvenMicroProgramId(MieleEnum):
    """Program Id codes for steam oven micro combo."""

    no_program = 0, -1
    steam_cooking = 8
    microwave = 19
    popcorn = 53
    quick_mw = 54
    sous_vide = 72
    eco_steam_cooking = 75
    rapid_steam_cooking = 77
    descale = 326
    menu_cooking = 330
    reheating_with_steam = 2018
    defrosting_with_steam = 2019
    blanching = 2020
    bottling = 2021
    sterilize_crockery = 2022
    prove_dough = 2023
    soak = 2027
    reheating_with_microwave = 2029
    defrosting_with_microwave = 2030
    artichokes_small = 2031
    artichokes_medium = 2032
    artichokes_large = 2033
    eggplant_sliced = 2034
    eggplant_diced = 2035
    cauliflower_whole_small = 2036
    cauliflower_whole_medium = 2039
    cauliflower_whole_large = 2042
    cauliflower_florets_small = 2046
    cauliflower_florets_medium = 2048
    cauliflower_florets_large = 2049
    green_beans_whole = 2051
    green_beans_cut = 2052
    yellow_beans_whole = 2053
    yellow_beans_cut = 2054
    broad_beans = 2055
    common_beans = 2056
    runner_beans_whole = 2057
    runner_beans_pieces = 2058
    runner_beans_sliced = 2059
    broccoli_whole_small = 2060
    broccoli_whole_medium = 2061
    broccoli_whole_large = 2062
    broccoli_florets_small = 2064
    broccoli_florets_medium = 2066
    broccoli_florets_large = 2068
    endive_halved = 2069
    endive_quartered = 2070
    endive_strips = 2071
    chinese_cabbage_cut = 2072
    peas = 2073
    fennel_halved = 2074
    fennel_quartered = 2075
    fennel_strips = 2076
    kale_cut = 2077
    potatoes_in_the_skin_waxy_small_steam_cooking = 2080
    potatoes_in_the_skin_waxy_small_rapid_steam_cooking = 2081
    potatoes_in_the_skin_waxy_medium_steam_cooking = 2083
    potatoes_in_the_skin_waxy_medium_rapid_steam_cooking = 2084
    potatoes_in_the_skin_waxy_large_steam_cooking = 2086
    potatoes_in_the_skin_waxy_large_rapid_steam_cooking = 2087
    potatoes_in_the_skin_floury_small = 2088
    potatoes_in_the_skin_floury_medium = 2091
    potatoes_in_the_skin_floury_large = 2094
    potatoes_in_the_skin_mainly_waxy_small = 2097
    potatoes_in_the_skin_mainly_waxy_medium = 2100
    potatoes_in_the_skin_mainly_waxy_large = 2103
    potatoes_waxy_whole_small = 2106
    potatoes_waxy_whole_medium = 2109
    potatoes_waxy_whole_large = 2112
    potatoes_waxy_halved = 2115
    potatoes_waxy_quartered = 2116
    potatoes_waxy_diced = 2117
    potatoes_mainly_waxy_small = 2118
    potatoes_mainly_waxy_medium = 2119
    potatoes_mainly_waxy_large = 2120
    potatoes_mainly_waxy_halved = 2121
    potatoes_mainly_waxy_quartered = 2122
    potatoes_mainly_waxy_diced = 2123
    potatoes_floury_whole_small = 2124
    potatoes_floury_whole_medium = 2125
    potatoes_floury_whole_large = 2126
    potatoes_floury_halved = 2127
    potatoes_floury_quartered = 2128
    potatoes_floury_diced = 2129
    german_turnip_sliced = 2130
    german_turnip_cut_into_batons = 2131
    german_turnip_diced = 2132
    pumpkin_diced = 2133
    corn_on_the_cob = 2134
    mangel_cut = 2135
    bunched_carrots_whole_small = 2136
    bunched_carrots_whole_medium = 2137
    bunched_carrots_whole_large = 2138
    bunched_carrots_halved = 2139
    bunched_carrots_quartered = 2140
    bunched_carrots_diced = 2141
    bunched_carrots_cut_into_batons = 2142
    bunched_carrots_sliced = 2143
    parisian_carrots_small = 2144
    parisian_carrots_medium = 2145
    parisian_carrots_large = 2146
    carrots_whole_small = 2147
    carrots_whole_medium = 2148
    carrots_whole_large = 2149
    carrots_halved = 2150
    carrots_quartered = 2151
    carrots_diced = 2152
    carrots_cut_into_batons = 2153
    carrots_sliced = 2155
    pepper_halved = 2156
    pepper_quartered = 2157
    pepper_strips = 2158
    pepper_diced = 2159
    parsnip_sliced = 2160
    parsnip_diced = 2161
    parsnip_cut_into_batons = 2162
    parsley_root_sliced = 2163
    parsley_root_diced = 2164
    parsley_root_cut_into_batons = 2165
    leek_pieces = 2166
    leek_rings = 2167
    romanesco_whole_small = 2168
    romanesco_whole_medium = 2169
    romanesco_whole_large = 2170
    romanesco_florets_small = 2171
    romanesco_florets_medium = 2172
    romanesco_florets_large = 2173
    brussels_sprout = 2175
    beetroot_whole_small = 2176
    beetroot_whole_medium = 2177
    beetroot_whole_large = 2178
    red_cabbage_cut = 2179
    black_salsify_thin = 2180
    black_salsify_medium = 2181
    black_salsify_thick = 2182
    celery_pieces = 2183
    celery_sliced = 2184
    celeriac_sliced = 2185
    celeriac_cut_into_batons = 2186
    celeriac_diced = 2187
    white_asparagus_thin = 2188
    white_asparagus_medium = 2189
    white_asparagus_thick = 2190
    green_asparagus_thin = 2192
    green_asparagus_medium = 2194
    green_asparagus_thick = 2196
    spinach = 2197
    pointed_cabbage_cut = 2198
    yam_halved = 2199
    yam_quartered = 2200
    yam_strips = 2201
    swede_diced = 2202
    swede_cut_into_batons = 2203
    teltow_turnip_sliced = 2204
    teltow_turnip_diced = 2205
    jerusalem_artichoke_sliced = 2206
    jerusalem_artichoke_diced = 2207
    green_cabbage_cut = 2208
    savoy_cabbage_cut = 2209
    courgette_sliced = 2210
    courgette_diced = 2211
    snow_pea = 2212
    perch_whole = 2214
    perch_fillet_2_cm = 2215
    perch_fillet_3_cm = 2216
    gilt_head_bream_whole = 2217
    gilt_head_bream_fillet = 2220
    codfish_piece = 2221, 2232
    codfish_fillet = 2222, 2231
    trout = 2224
    pike_fillet = 2225
    pike_piece = 2226
    halibut_fillet_2_cm = 2227
    halibut_fillet_3_cm = 2230
    carp = 2233
    salmon_fillet_2_cm = 2234
    salmon_fillet_3_cm = 2235
    salmon_steak_2_cm = 2238
    salmon_steak_3_cm = 2239
    salmon_piece = 2240
    salmon_trout = 2241
    iridescent_shark_fillet = 2244
    red_snapper_fillet_2_cm = 2245
    red_snapper_fillet_3_cm = 2248
    redfish_fillet_2_cm = 2249
    redfish_fillet_3_cm = 2250
    redfish_piece = 2251
    char = 2252
    plaice_whole_2_cm = 2253
    plaice_whole_3_cm = 2254
    plaice_whole_4_cm = 2255
    plaice_fillet_1_cm = 2256
    plaice_fillet_2_cm = 2259
    coalfish_fillet_2_cm = 2260
    coalfish_fillet_3_cm = 2261
    coalfish_piece = 2262
    sea_devil_fillet_3_cm = 2263
    sea_devil_fillet_4_cm = 2266
    common_sole_fillet_1_cm = 2267
    common_sole_fillet_2_cm = 2270
    atlantic_catfish_fillet_1_cm = 2271
    atlantic_catfish_fillet_2_cm = 2272
    turbot_fillet_2_cm = 2273
    turbot_fillet_3_cm = 2276
    tuna_steak = 2277
    tuna_fillet_2_cm = 2278
    tuna_fillet_3_cm = 2279
    tilapia_fillet_1_cm = 2280
    tilapia_fillet_2_cm = 2281
    nile_perch_fillet_2_cm = 2282
    nile_perch_fillet_3_cm = 2283
    zander_fillet = 2285
    soup_hen = 2288
    poularde_whole = 2291
    poularde_breast = 2292
    turkey_breast = 2294
    chicken_tikka_masala_with_rice = 2302
    veal_fillet_whole = 2312
    veal_fillet_medaillons_1_cm = 2313
    veal_fillet_medaillons_2_cm = 2315
    veal_fillet_medaillons_3_cm = 2317
    goulash_soup = 2324
    dutch_hash = 2327
    stuffed_cabbage = 2328
    beef_tenderloin = 2330
    beef_tenderloin_medaillons_1_cm_steam_cooking = 2333
    beef_tenderloin_medaillons_2_cm_steam_cooking = 2334
    beef_tenderloin_medaillons_3_cm_steam_cooking = 2335
    silverside_5_cm = 2339
    silverside_7_5_cm = 2342
    silverside_10_cm = 2345
    meat_for_soup_back_or_top_rib = 2348
    meat_for_soup_leg_steak = 2349
    meat_for_soup_brisket = 2350
    viennese_silverside = 2353
    whole_ham_steam_cooking = 2354
    whole_ham_reheating = 2355
    kasseler_piece = 2359
    kasseler_slice = 2361
    knuckle_of_pork_fresh = 2363
    knuckle_of_pork_cured = 2364
    pork_tenderloin_medaillons_3_cm = 2367
    pork_tenderloin_medaillons_4_cm = 2368
    pork_tenderloin_medaillons_5_cm = 2369
    pumpkin_soup = 2429
    meat_with_rice = 2430
    beef_casserole = 2431
    risotto = 2450, 2451
    rice_pudding_steam_cooking = 2453
    rice_pudding_rapid_steam_cooking = 2454
    amaranth = 2461
    bulgur = 2462
    spelt_whole = 2463
    spelt_cracked = 2464
    green_spelt_whole = 2465
    green_spelt_cracked = 2466
    oats_whole = 2467
    oats_cracked = 2468
    millet = 2469
    quinoa = 2470
    polenta_swiss_style_fine_polenta = 2471
    polenta_swiss_style_medium_polenta = 2472
    polenta_swiss_style_coarse_polenta = 2473
    polenta = 2474
    rye_whole = 2475
    rye_cracked = 2476
    wheat_whole = 2477
    wheat_cracked = 2478
    gnocchi_fresh = 2480
    yeast_dumplings_fresh = 2481
    potato_dumplings_raw_boil_in_bag = 2482
    potato_dumplings_raw_deep_frozen = 2483
    potato_dumplings_half_half_boil_in_bag = 2484
    potato_dumplings_half_half_deep_frozen = 2485
    bread_dumplings_boil_in_the_bag = 2486
    bread_dumplings_fresh = 2487
    ravioli_fresh = 2488
    spaetzle_fresh = 2489
    tagliatelli_fresh = 2490
    schupfnudeln_potato_noodels = 2491
    tortellini_fresh = 2492
    red_lentils = 2493
    brown_lentils = 2494
    beluga_lentils = 2495
    green_split_peas = 2496
    yellow_split_peas = 2497
    chick_peas = 2498
    white_beans = 2499
    pinto_beans = 2500
    red_beans = 2501
    black_beans = 2502
    hens_eggs_size_s_soft = 2503
    hens_eggs_size_s_medium = 2504
    hens_eggs_size_s_hard = 2505
    hens_eggs_size_m_soft = 2506
    hens_eggs_size_m_medium = 2507
    hens_eggs_size_m_hard = 2508
    hens_eggs_size_l_soft = 2509
    hens_eggs_size_l_medium = 2510
    hens_eggs_size_l_hard = 2511
    hens_eggs_size_xl_soft = 2512
    hens_eggs_size_xl_medium = 2513
    hens_eggs_size_xl_hard = 2514
    swiss_toffee_cream_100_ml = 2515
    swiss_toffee_cream_150_ml = 2516
    toffee_date_dessert_several_small = 2518
    cheesecake_several_small = 2520
    cheesecake_one_large = 2521
    christmas_pudding_cooking = 2522
    christmas_pudding_heating = 2523
    treacle_sponge_pudding_several_small = 2524
    treacle_sponge_pudding_one_large = 2525
    sweet_cheese_dumplings = 2526
    apples_whole = 2527
    apples_halved = 2528
    apples_quartered = 2529
    apples_sliced = 2530
    apples_diced = 2531
    apricots_halved_steam_cooking = 2532
    apricots_halved_skinning = 2533
    apricots_quartered = 2534
    apricots_wedges = 2535
    pears_halved = 2536
    pears_quartered = 2537
    pears_wedges = 2538
    sweet_cherries = 2539
    sour_cherries = 2540
    pears_to_cook_small_whole = 2541
    pears_to_cook_small_halved = 2542
    pears_to_cook_small_quartered = 2543
    pears_to_cook_medium_whole = 2544
    pears_to_cook_medium_halved = 2545
    pears_to_cook_medium_quartered = 2546
    pears_to_cook_large_whole = 2547
    pears_to_cook_large_halved = 2548
    pears_to_cook_large_quartered = 2549
    mirabelles = 2550
    nectarines_peaches_halved_steam_cooking = 2551
    nectarines_peaches_halved_skinning = 2552
    nectarines_peaches_quartered = 2553
    nectarines_peaches_wedges = 2554
    plums_whole = 2555
    plums_halved = 2556
    cranberries = 2557
    quinces_diced = 2558
    greenage_plums = 2559
    rhubarb_chunks = 2560
    gooseberries = 2561
    mushrooms_whole = 2562
    mushrooms_halved = 2563
    mushrooms_sliced = 2564
    mushrooms_quartered = 2565
    mushrooms_diced = 2566
    cep = 2567
    chanterelle = 2568
    oyster_mushroom_whole = 2569
    oyster_mushroom_strips = 2570
    oyster_mushroom_diced = 2571
    saucisson = 2572
    bruehwurst_sausages = 2573
    bologna_sausage = 2574
    veal_sausages = 2575
    crevettes = 2577
    prawns = 2579
    king_prawns = 2581
    small_shrimps = 2583
    large_shrimps = 2585
    mussels = 2587
    scallops = 2589
    venus_clams = 2591
    goose_barnacles = 2592
    cockles = 2593
    razor_clams_small = 2594
    razor_clams_medium = 2595
    razor_clams_large = 2596
    mussels_in_sauce = 2597
    bottling_soft = 2598
    bottling_medium = 2599
    bottling_hard = 2600
    melt_chocolate = 2601
    dissolve_gelatine = 2602
    sweat_onions = 2603
    cook_bacon = 2604
    heating_damp_flannels = 2605
    decrystallize_honey = 2606
    make_yoghurt = 2607
    toffee_date_dessert_one_large = 2687
    beef_tenderloin_medaillons_1_cm_low_temperature_cooking = 2694
    beef_tenderloin_medaillons_2_cm_low_temperature_cooking = 2695
    beef_tenderloin_medaillons_3_cm_low_temperature_cooking = 2696
    wild_rice = 3373
    wholegrain_rice = 3376
    parboiled_rice_steam_cooking = 3380
    parboiled_rice_rapid_steam_cooking = 3381
    basmati_rice_steam_cooking = 3383
    basmati_rice_rapid_steam_cooking = 3384
    jasmine_rice_steam_cooking = 3386
    jasmine_rice_rapid_steam_cooking = 3387
    huanghuanian_steam_cooking = 3389
    huanghuanian_rapid_steam_cooking = 3390
    simiao_steam_cooking = 3392
    simiao_rapid_steam_cooking = 3393
    long_grain_rice_general_steam_cooking = 3395
    long_grain_rice_general_rapid_steam_cooking = 3396
    chongming_steam_cooking = 3398
    chongming_rapid_steam_cooking = 3399
    wuchang_steam_cooking = 3401
    wuchang_rapid_steam_cooking = 3402
    uonumma_koshihikari_steam_cooking = 3404
    uonumma_koshihikari_rapid_steam_cooking = 3405
    sheyang_steam_cooking = 3407
    sheyang_rapid_steam_cooking = 3408
    round_grain_rice_general_steam_cooking = 3410
    round_grain_rice_general_rapid_steam_cooking = 3411
    missing2none = -9999


PROGRAM_IDS: dict[int, type[MieleEnum]] = {
    MieleAppliance.WASHING_MACHINE: WashingMachineProgramId,
    MieleAppliance.TUMBLE_DRYER: TumbleDryerProgramId,
    MieleAppliance.DISHWASHER: DishWasherProgramId,
    MieleAppliance.DISH_WARMER: DishWarmerProgramId,
    MieleAppliance.OVEN: OvenProgramId,
    MieleAppliance.OVEN_MICROWAVE: OvenProgramId,
    MieleAppliance.STEAM_OVEN_MK2: OvenProgramId,
    MieleAppliance.STEAM_OVEN: OvenProgramId,
    MieleAppliance.STEAM_OVEN_COMBI: OvenProgramId,
    MieleAppliance.STEAM_OVEN_MICRO: SteamOvenMicroProgramId,
    MieleAppliance.WASHER_DRYER: WashingMachineProgramId,
    MieleAppliance.ROBOT_VACUUM_CLEANER: RobotVacuumCleanerProgramId,
    MieleAppliance.COFFEE_SYSTEM: CoffeeSystemProgramId,
}

COFFEE_SYSTEM_PROFILE: dict[range, str] = {
    range(24000, 24032): "profile_1",
    range(24032, 24064): "profile_2",
    range(24064, 24096): "profile_3",
    range(24096, 24128): "profile_4",
    range(24128, 24160): "profile_5",
}

# STEAM_OVEN_MICRO_PROGRAM_ID: dict[int, str] = {
#     8: "steam_cooking",
#     19: "microwave",
#     53: "popcorn",
#     54: "quick_mw",
#     72: "sous_vide",
#     75: "eco_steam_cooking",
#     77: "rapid_steam_cooking",
#     97: "custom_program_1",
#     98: "custom_program_2",
#     99: "custom_program_3",
#     100: "custom_program_4",
#     101: "custom_program_5",
#     102: "custom_program_6",
#     103: "custom_program_7",
#     104: "custom_program_8",
#     105: "custom_program_9",
#     106: "custom_program_10",
#     107: "custom_program_11",
#     108: "custom_program_12",
#     109: "custom_program_13",
#     110: "custom_program_14",
#     111: "custom_program_15",
#     112: "custom_program_16",
#     113: "custom_program_17",
#     114: "custom_program_18",
#     115: "custom_program_19",
#     116: "custom_program_20",
#     326: "descale",
#     330: "menu_cooking",
#     2018: "reheating_with_steam",
#     2019: "defrosting_with_steam",
#     2020: "blanching",
#     2021: "bottling",
#     2022: "sterilize_crockery",
#     2023: "prove_dough",
#     2027: "soak",
#     2029: "reheating_with_microwave",
#     2030: "defrosting_with_microwave",
#     2031: "artichokes_small",
#     2032: "artichokes_medium",
#     2033: "artichokes_large",
#     2034: "eggplant_sliced",
#     2035: "eggplant_diced",
#     2036: "cauliflower_whole_small",
#     2039: "cauliflower_whole_medium",
#     2042: "cauliflower_whole_large",
#     2046: "cauliflower_florets_small",
#     2048: "cauliflower_florets_medium",
#     2049: "cauliflower_florets_large",
#     2051: "green_beans_whole",
#     2052: "green_beans_cut",
#     2053: "yellow_beans_whole",
#     2054: "yellow_beans_cut",
#     2055: "broad_beans",
#     2056: "common_beans",
#     2057: "runner_beans_whole",
#     2058: "runner_beans_pieces",
#     2059: "runner_beans_sliced",
#     2060: "broccoli_whole_small",
#     2061: "broccoli_whole_medium",
#     2062: "broccoli_whole_large",
#     2064: "broccoli_florets_small",
#     2066: "broccoli_florets_medium",
#     2068: "broccoli_florets_large",
#     2069: "endive_halved",
#     2070: "endive_quartered",
#     2071: "endive_strips",
#     2072: "chinese_cabbage_cut",
#     2073: "peas",
#     2074: "fennel_halved",
#     2075: "fennel_quartered",
#     2076: "fennel_strips",
#     2077: "kale_cut",
#     2080: "potatoes_in_the_skin_waxy_small_steam_cooking",
#     2081: "potatoes_in_the_skin_waxy_small_rapid_steam_cooking",
#     2083: "potatoes_in_the_skin_waxy_medium_steam_cooking",
#     2084: "potatoes_in_the_skin_waxy_medium_rapid_steam_cooking",
#     2086: "potatoes_in_the_skin_waxy_large_steam_cooking",
#     2087: "potatoes_in_the_skin_waxy_large_rapid_steam_cooking",
#     2088: "potatoes_in_the_skin_floury_small",
#     2091: "potatoes_in_the_skin_floury_medium",
#     2094: "potatoes_in_the_skin_floury_large",
#     2097: "potatoes_in_the_skin_mainly_waxy_small",
#     2100: "potatoes_in_the_skin_mainly_waxy_medium",
#     2103: "potatoes_in_the_skin_mainly_waxy_large",
#     2106: "potatoes_waxy_whole_small",
#     2109: "potatoes_waxy_whole_medium",
#     2112: "potatoes_waxy_whole_large",
#     2115: "potatoes_waxy_halved",
#     2116: "potatoes_waxy_quartered",
#     2117: "potatoes_waxy_diced",
#     2118: "potatoes_mainly_waxy_small",
#     2119: "potatoes_mainly_waxy_medium",
#     2120: "potatoes_mainly_waxy_large",
#     2121: "potatoes_mainly_waxy_halved",
#     2122: "potatoes_mainly_waxy_quartered",
#     2123: "potatoes_mainly_waxy_diced",
#     2124: "potatoes_floury_whole_small",
#     2125: "potatoes_floury_whole_medium",
#     2126: "potatoes_floury_whole_large",
#     2127: "potatoes_floury_halved",
#     2128: "potatoes_floury_quartered",
#     2129: "potatoes_floury_diced",
#     2130: "german_turnip_sliced",
#     2131: "german_turnip_cut_into_batons",
#     2132: "german_turnip_diced",
#     2133: "pumpkin_diced",
#     2134: "corn_on_the_cob",
#     2135: "mangel_cut",
#     2136: "bunched_carrots_whole_small",
#     2137: "bunched_carrots_whole_medium",
#     2138: "bunched_carrots_whole_large",
#     2139: "bunched_carrots_halved",
#     2140: "bunched_carrots_quartered",
#     2141: "bunched_carrots_diced",
#     2142: "bunched_carrots_cut_into_batons",
#     2143: "bunched_carrots_sliced",
#     2144: "parisian_carrots_small",
#     2145: "parisian_carrots_medium",
#     2146: "parisian_carrots_large",
#     2147: "carrots_whole_small",
#     2148: "carrots_whole_medium",
#     2149: "carrots_whole_large",
#     2150: "carrots_halved",
#     2151: "carrots_quartered",
#     2152: "carrots_diced",
#     2153: "carrots_cut_into_batons",
#     2155: "carrots_sliced",
#     2156: "pepper_halved",
#     2157: "pepper_quartered",
#     2158: "pepper_strips",
#     2159: "pepper_diced",
#     2160: "parsnip_sliced",
#     2161: "parsnip_diced",
#     2162: "parsnip_cut_into_batons",
#     2163: "parsley_root_sliced",
#     2164: "parsley_root_diced",
#     2165: "parsley_root_cut_into_batons",
#     2166: "leek_pieces",
#     2167: "leek_rings",
#     2168: "romanesco_whole_small",
#     2169: "romanesco_whole_medium",
#     2170: "romanesco_whole_large",
#     2171: "romanesco_florets_small",
#     2172: "romanesco_florets_medium",
#     2173: "romanesco_florets_large",
#     2175: "brussels_sprout",
#     2176: "beetroot_whole_small",
#     2177: "beetroot_whole_medium",
#     2178: "beetroot_whole_large",
#     2179: "red_cabbage_cut",
#     2180: "black_salsify_thin",
#     2181: "black_salsify_medium",
#     2182: "black_salsify_thick",
#     2183: "celery_pieces",
#     2184: "celery_sliced",
#     2185: "celeriac_sliced",
#     2186: "celeriac_cut_into_batons",
#     2187: "celeriac_diced",
#     2188: "white_asparagus_thin",
#     2189: "white_asparagus_medium",
#     2190: "white_asparagus_thick",
#     2192: "green_asparagus_thin",
#     2194: "green_asparagus_medium",
#     2196: "green_asparagus_thick",
#     2197: "spinach",
#     2198: "pointed_cabbage_cut",
#     2199: "yam_halved",
#     2200: "yam_quartered",
#     2201: "yam_strips",
#     2202: "swede_diced",
#     2203: "swede_cut_into_batons",
#     2204: "teltow_turnip_sliced",
#     2205: "teltow_turnip_diced",
#     2206: "jerusalem_artichoke_sliced",
#     2207: "jerusalem_artichoke_diced",
#     2208: "green_cabbage_cut",
#     2209: "savoy_cabbage_cut",
#     2210: "courgette_sliced",
#     2211: "courgette_diced",
#     2212: "snow_pea",
#     2214: "perch_whole",
#     2215: "perch_fillet_2_cm",
#     2216: "perch_fillet_3_cm",
#     2217: "gilt_head_bream_whole",
#     2220: "gilt_head_bream_fillet",
#     2221: "codfish_piece",
#     2222: "codfish_fillet",
#     2224: "trout",
#     2225: "pike_fillet",
#     2226: "pike_piece",
#     2227: "halibut_fillet_2_cm",
#     2230: "halibut_fillet_3_cm",
#     2231: "codfish_fillet",
#     2232: "codfish_piece",
#     2233: "carp",
#     2234: "salmon_fillet_2_cm",
#     2235: "salmon_fillet_3_cm",
#     2238: "salmon_steak_2_cm",
#     2239: "salmon_steak_3_cm",
#     2240: "salmon_piece",
#     2241: "salmon_trout",
#     2244: "iridescent_shark_fillet",
#     2245: "red_snapper_fillet_2_cm",
#     2248: "red_snapper_fillet_3_cm",
#     2249: "redfish_fillet_2_cm",
#     2250: "redfish_fillet_3_cm",
#     2251: "redfish_piece",
#     2252: "char",
#     2253: "plaice_whole_2_cm",
#     2254: "plaice_whole_3_cm",
#     2255: "plaice_whole_4_cm",
#     2256: "plaice_fillet_1_cm",
#     2259: "plaice_fillet_2_cm",
#     2260: "coalfish_fillet_2_cm",
#     2261: "coalfish_fillet_3_cm",
#     2262: "coalfish_piece",
#     2263: "sea_devil_fillet_3_cm",
#     2266: "sea_devil_fillet_4_cm",
#     2267: "common_sole_fillet_1_cm",
#     2270: "common_sole_fillet_2_cm",
#     2271: "atlantic_catfish_fillet_1_cm",
#     2272: "atlantic_catfish_fillet_2_cm",
#     2273: "turbot_fillet_2_cm",
#     2276: "turbot_fillet_3_cm",
#     2277: "tuna_steak",
#     2278: "tuna_fillet_2_cm",
#     2279: "tuna_fillet_3_cm",
#     2280: "tilapia_fillet_1_cm",
#     2281: "tilapia_fillet_2_cm",
#     2282: "nile_perch_fillet_2_cm",
#     2283: "nile_perch_fillet_3_cm",
#     2285: "zander_fillet",
#     2288: "soup_hen",
#     2291: "poularde_whole",
#     2292: "poularde_breast",
#     2294: "turkey_breast",
#     2302: "chicken_tikka_masala_with_rice",
#     2312: "veal_fillet_whole",
#     2313: "veal_fillet_medaillons_1_cm",
#     2315: "veal_fillet_medaillons_2_cm",
#     2317: "veal_fillet_medaillons_3_cm",
#     2324: "goulash_soup",
#     2327: "dutch_hash",
#     2328: "stuffed_cabbage",
#     2330: "beef_tenderloin",
#     2333: "beef_tenderloin_medaillons_1_cm_steam_cooking",
#     2334: "beef_tenderloin_medaillons_2_cm_steam_cooking",
#     2335: "beef_tenderloin_medaillons_3_cm_steam_cooking",
#     2339: "silverside_5_cm",
#     2342: "silverside_7_5_cm",
#     2345: "silverside_10_cm",
#     2348: "meat_for_soup_back_or_top_rib",
#     2349: "meat_for_soup_leg_steak",
#     2350: "meat_for_soup_brisket",
#     2353: "viennese_silverside",
#     2354: "whole_ham_steam_cooking",
#     2355: "whole_ham_reheating",
#     2359: "kasseler_piece",
#     2361: "kasseler_slice",
#     2363: "knuckle_of_pork_fresh",
#     2364: "knuckle_of_pork_cured",
#     2367: "pork_tenderloin_medaillons_3_cm",
#     2368: "pork_tenderloin_medaillons_4_cm",
#     2369: "pork_tenderloin_medaillons_5_cm",
#     2429: "pumpkin_soup",
#     2430: "meat_with_rice",
#     2431: "beef_casserole",
#     2450: "pumpkin_risotto",
#     2451: "risotto",
#     2453: "rice_pudding_steam_cooking",
#     2454: "rice_pudding_rapid_steam_cooking",
#     2461: "amaranth",
#     2462: "bulgur",
#     2463: "spelt_whole",
#     2464: "spelt_cracked",
#     2465: "green_spelt_whole",
#     2466: "green_spelt_cracked",
#     2467: "oats_whole",
#     2468: "oats_cracked",
#     2469: "millet",
#     2470: "quinoa",
#     2471: "polenta_swiss_style_fine_polenta",
#     2472: "polenta_swiss_style_medium_polenta",
#     2473: "polenta_swiss_style_coarse_polenta",
#     2474: "polenta",
#     2475: "rye_whole",
#     2476: "rye_cracked",
#     2477: "wheat_whole",
#     2478: "wheat_cracked",
#     2480: "gnocchi_fresh",
#     2481: "yeast_dumplings_fresh",
#     2482: "potato_dumplings_raw_boil_in_bag",
#     2483: "potato_dumplings_raw_deep_frozen",
#     2484: "potato_dumplings_half_half_boil_in_bag",
#     2485: "potato_dumplings_half_half_deep_frozen",
#     2486: "bread_dumplings_boil_in_the_bag",
#     2487: "bread_dumplings_fresh",
#     2488: "ravioli_fresh",
#     2489: "spaetzle_fresh",
#     2490: "tagliatelli_fresh",
#     2491: "schupfnudeln_potato_noodels",
#     2492: "tortellini_fresh",
#     2493: "red_lentils",
#     2494: "brown_lentils",
#     2495: "beluga_lentils",
#     2496: "green_split_peas",
#     2497: "yellow_split_peas",
#     2498: "chick_peas",
#     2499: "white_beans",
#     2500: "pinto_beans",
#     2501: "red_beans",
#     2502: "black_beans",
#     2503: "hens_eggs_size_s_soft",
#     2504: "hens_eggs_size_s_medium",
#     2505: "hens_eggs_size_s_hard",
#     2506: "hens_eggs_size_m_soft",
#     2507: "hens_eggs_size_m_medium",
#     2508: "hens_eggs_size_m_hard",
#     2509: "hens_eggs_size_l_soft",
#     2510: "hens_eggs_size_l_medium",
#     2511: "hens_eggs_size_l_hard",
#     2512: "hens_eggs_size_xl_soft",
#     2513: "hens_eggs_size_xl_medium",
#     2514: "hens_eggs_size_xl_hard",
#     2515: "swiss_toffee_cream_100_ml",
#     2516: "swiss_toffee_cream_150_ml",
#     2518: "toffee_date_dessert_several_small",
#     2520: "cheesecake_several_small",
#     2521: "cheesecake_one_large",
#     2522: "christmas_pudding_cooking",
#     2523: "christmas_pudding_heating",
#     2524: "treacle_sponge_pudding_several_small",
#     2525: "treacle_sponge_pudding_one_large",
#     2526: "sweet_cheese_dumplings",
#     2527: "apples_whole",
#     2528: "apples_halved",
#     2529: "apples_quartered",
#     2530: "apples_sliced",
#     2531: "apples_diced",
#     2532: "apricots_halved_steam_cooking",
#     2533: "apricots_halved_skinning",
#     2534: "apricots_quartered",
#     2535: "apricots_wedges",
#     2536: "pears_halved",
#     2537: "pears_quartered",
#     2538: "pears_wedges",
#     2539: "sweet_cherries",
#     2540: "sour_cherries",
#     2541: "pears_to_cook_small_whole",
#     2542: "pears_to_cook_small_halved",
#     2543: "pears_to_cook_small_quartered",
#     2544: "pears_to_cook_medium_whole",
#     2545: "pears_to_cook_medium_halved",
#     2546: "pears_to_cook_medium_quartered",
#     2547: "pears_to_cook_large_whole",
#     2548: "pears_to_cook_large_halved",
#     2549: "pears_to_cook_large_quartered",
#     2550: "mirabelles",
#     2551: "nectarines_peaches_halved_steam_cooking",
#     2552: "nectarines_peaches_halved_skinning",
#     2553: "nectarines_peaches_quartered",
#     2554: "nectarines_peaches_wedges",
#     2555: "plums_whole",
#     2556: "plums_halved",
#     2557: "cranberries",
#     2558: "quinces_diced",
#     2559: "greenage_plums",
#     2560: "rhubarb_chunks",
#     2561: "gooseberries",
#     2562: "mushrooms_whole",
#     2563: "mushrooms_halved",
#     2564: "mushrooms_sliced",
#     2565: "mushrooms_quartered",
#     2566: "mushrooms_diced",
#     2567: "cep",
#     2568: "chanterelle",
#     2569: "oyster_mushroom_whole",
#     2570: "oyster_mushroom_strips",
#     2571: "oyster_mushroom_diced",
#     2572: "saucisson",
#     2573: "bruehwurst_sausages",
#     2574: "bologna_sausage",
#     2575: "veal_sausages",
#     2577: "crevettes",
#     2579: "prawns",
#     2581: "king_prawns",
#     2583: "small_shrimps",
#     2585: "large_shrimps",
#     2587: "mussels",
#     2589: "scallops",
#     2591: "venus_clams",
#     2592: "goose_barnacles",
#     2593: "cockles",
#     2594: "razor_clams_small",
#     2595: "razor_clams_medium",
#     2596: "razor_clams_large",
#     2597: "mussels_in_sauce",
#     2598: "bottling_soft",
#     2599: "bottling_medium",
#     2600: "bottling_hard",
#     2601: "melt_chocolate",
#     2602: "dissolve_gelatine",
#     2603: "sweat_onions",
#     2604: "cook_bacon",
#     2605: "heating_damp_flannels",
#     2606: "decrystallise_honey",
#     2607: "make_yoghurt",
#     2687: "toffee_date_dessert_one_large",
#     2694: "beef_tenderloin_medaillons_1_cm_low_temperature_cooking",
#     2695: "beef_tenderloin_medaillons_2_cm_low_temperature_cooking",
#     2696: "beef_tenderloin_medaillons_3_cm_low_temperature_cooking",
#     3373: "wild_rice",
#     3376: "wholegrain_rice",
#     3380: "parboiled_rice_steam_cooking",
#     3381: "parboiled_rice_rapid_steam_cooking",
#     3383: "basmati_rice_steam_cooking",
#     3384: "basmati_rice_rapid_steam_cooking",
#     3386: "jasmine_rice_steam_cooking",
#     3387: "jasmine_rice_rapid_steam_cooking",
#     3389: "huanghuanian_steam_cooking",
#     3390: "huanghuanian_rapid_steam_cooking",
#     3392: "simiao_steam_cooking",
#     3393: "simiao_rapid_steam_cooking",
#     3395: "long_grain_rice_general_steam_cooking",
#     3396: "long_grain_rice_general_rapid_steam_cooking",
#     3398: "chongming_steam_cooking",
#     3399: "chongming_rapid_steam_cooking",
#     3401: "wuchang_steam_cooking",
#     3402: "wuchang_rapid_steam_cooking",
#     3404: "uonumma_koshihikari_steam_cooking",
#     3405: "uonumma_koshihikari_rapid_steam_cooking",
#     3407: "sheyang_steam_cooking",
#     3408: "sheyang_rapid_steam_cooking",
#     3410: "round_grain_rice_general_steam_cooking",
#     3411: "round_grain_rice_general_rapid_steam_cooking",
# }

# STATE_PROGRAM_ID: dict[int, dict[int, str]] = {
#     MieleAppliance.WASHING_MACHINE: WASHING_MACHINE_PROGRAM_ID,
#     MieleAppliance.TUMBLE_DRYER: TUMBLE_DRYER_PROGRAM_ID,
#     MieleAppliance.DISHWASHER: DISHWASHER_PROGRAM_ID,
#     MieleAppliance.DISH_WARMER: DISH_WARMER_PROGRAM_ID,
#     MieleAppliance.OVEN: OVEN_PROGRAM_ID,
#     MieleAppliance.OVEN_MICROWAVE: OVEN_PROGRAM_ID | STEAM_OVEN_MICRO_PROGRAM_ID,
#     MieleAppliance.STEAM_OVEN_MK2: OVEN_PROGRAM_ID | STEAM_OVEN_MICRO_PROGRAM_ID,
#     MieleAppliance.STEAM_OVEN_COMBI: OVEN_PROGRAM_ID | STEAM_OVEN_MICRO_PROGRAM_ID,
#     MieleAppliance.STEAM_OVEN: STEAM_OVEN_MICRO_PROGRAM_ID,
#     MieleAppliance.STEAM_OVEN_MICRO: STEAM_OVEN_MICRO_PROGRAM_ID,
#     MieleAppliance.WASHER_DRYER: WASHING_MACHINE_PROGRAM_ID,
#     MieleAppliance.ROBOT_VACUUM_CLEANER: ROBOT_VACUUM_CLEANER_PROGRAM_ID,
#     MieleAppliance.COFFEE_SYSTEM: COFFEE_SYSTEM_PROGRAM_ID,
# }


class PlatePowerStep(MieleEnum, missing_to_none=True):
    """Plate power settings."""

    plate_step_0 = 0
    plate_step_warming = 110, 220
    plate_step_1 = 1
    plate_step_2 = 2
    plate_step_3 = 3
    plate_step_4 = 4
    plate_step_5 = 5
    plate_step_6 = 6
    plate_step_7 = 7
    plate_step_8 = 8
    plate_step_9 = 9
    plate_step_10 = 10
    plate_step_11 = 11
    plate_step_12 = 12
    plate_step_13 = 13
    plate_step_14 = 14
    plate_step_15 = 15
    plate_step_16 = 16
    plate_step_17 = 17
    plate_step_18 = 18
    plate_step_boost = 117, 118, 218
    plate_step_boost_2 = 217

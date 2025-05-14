"""Constants for the Miele integration."""

from enum import IntEnum
import logging

from pymiele import MieleEnum

DOMAIN = "miele"
MANUFACTURER = "Miele"

ACTIONS = "actions"
POWER_ON = "powerOn"
POWER_OFF = "powerOff"
PROCESS_ACTION = "processAction"
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

_LOGGER = logging.getLogger(__name__)

completed_warnings: set[str] = set()


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
    missing2none = -9999


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
    missing2none = -9999


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
    missing2none = -9999


class ProgramPhaseOven(MieleEnum):
    """Program phase codes for ovens."""

    not_running = 0, 65535
    heating_up = 3073
    process_running = 3074
    process_finished = 3078
    energy_save = 3084
    missing2none = -9999


class ProgramPhaseWarmingDrawer(MieleEnum):
    """Program phase codes for warming drawers."""

    not_running = 0, 65535
    heating_up = 3073
    door_open = 3075
    keeping_warm = 3094
    cooling_down = 3088
    missing2none = -9999


class ProgramPhaseMicrowave(MieleEnum):
    """Program phase for microwave units."""

    not_running = 0, 65535
    heating = 3329
    process_running = 3330
    process_finished = 3334
    energy_save = 3340
    missing2none = -9999


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
    z_2nd_espresso = 4385
    z_2nd_pre_brewing = 4393
    z_2nd_grinding = 4401
    rinse = 4405
    missing2none = -9999


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
    missing2none = -9999


class ProgramPhaseMicrowaveOvenCombo(MieleEnum):
    """Program phase codes for microwave oven combo."""

    not_running = 0, 65535
    steam_reduction = 3863
    process_running = 7938
    waiting_for_start = 7939
    heating_up_phase = 7940
    process_finished = 7942
    missing2none = -9999


PROGRAM_PHASE: dict[int, type[MieleEnum]] = {
    MieleAppliance.WASHING_MACHINE: ProgramPhaseWashingMachine,
    MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL: ProgramPhaseWashingMachine,
    MieleAppliance.WASHING_MACHINE_PROFESSIONAL: ProgramPhaseWashingMachine,
    MieleAppliance.TUMBLE_DRYER: ProgramPhaseTumbleDryer,
    MieleAppliance.DRYER_PROFESSIONAL: ProgramPhaseTumbleDryer,
    MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL: ProgramPhaseTumbleDryer,
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
    missing2none = -9999


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
    cottons = 2, 20, 90
    minimum_iron = 3, 30
    woollens_handcare = 4, 40
    delicates = 5, 50
    warm_air = 6, 60
    express = 8, 80
    automatic_plus = 10
    cottons_hygiene = 23
    bed_linen = 31, 99002
    eco = 66
    cool_air = 70
    gentle_smoothing = 100
    proofing = 120
    denim = 130
    gentle_denim = 131
    sportswear = 150
    outerwear = 160
    silks_handcare = 170
    standard_pillows = 190
    basket_program = 220
    smoothing = 240
    steam_smoothing = 99001
    cottons_eco = 99003
    shirts = 99004
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


PROGRAM_ID: dict[int, type[MieleEnum]] = {
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

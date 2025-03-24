"""Constants for the Home Connect integration."""

from typing import cast

from aiohomeconnect.model import EventKey, OptionKey, ProgramKey, SettingKey, StatusKey

from homeassistant.const import UnitOfTemperature, UnitOfTime, UnitOfVolume

from .utils import bsh_key_to_translation_key

DOMAIN = "home_connect"

API_DEFAULT_RETRY_AFTER = 60

APPLIANCES_WITH_PROGRAMS = (
    "CleaningRobot",
    "CoffeeMaker",
    "Dishwasher",
    "Dryer",
    "Hood",
    "Oven",
    "WarmingDrawer",
    "Washer",
    "WasherDryer",
)

UNIT_MAP = {
    "seconds": UnitOfTime.SECONDS,
    "ml": UnitOfVolume.MILLILITERS,
    "°C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
}


BSH_POWER_ON = "BSH.Common.EnumType.PowerState.On"
BSH_POWER_OFF = "BSH.Common.EnumType.PowerState.Off"
BSH_POWER_STANDBY = "BSH.Common.EnumType.PowerState.Standby"


BSH_EVENT_PRESENT_STATE_PRESENT = "BSH.Common.EnumType.EventPresentState.Present"
BSH_EVENT_PRESENT_STATE_CONFIRMED = "BSH.Common.EnumType.EventPresentState.Confirmed"
BSH_EVENT_PRESENT_STATE_OFF = "BSH.Common.EnumType.EventPresentState.Off"


BSH_OPERATION_STATE_RUN = "BSH.Common.EnumType.OperationState.Run"
BSH_OPERATION_STATE_PAUSE = "BSH.Common.EnumType.OperationState.Pause"
BSH_OPERATION_STATE_FINISHED = "BSH.Common.EnumType.OperationState.Finished"


REFRIGERATION_STATUS_DOOR_CLOSED = "Refrigeration.Common.EnumType.Door.States.Closed"
REFRIGERATION_STATUS_DOOR_OPEN = "Refrigeration.Common.EnumType.Door.States.Open"


BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR = (
    "BSH.Common.EnumType.AmbientLightColor.CustomColor"
)


BSH_DOOR_STATE_CLOSED = "BSH.Common.EnumType.DoorState.Closed"
BSH_DOOR_STATE_LOCKED = "BSH.Common.EnumType.DoorState.Locked"
BSH_DOOR_STATE_OPEN = "BSH.Common.EnumType.DoorState.Open"


SERVICE_OPTION_ACTIVE = "set_option_active"
SERVICE_OPTION_SELECTED = "set_option_selected"
SERVICE_PAUSE_PROGRAM = "pause_program"
SERVICE_RESUME_PROGRAM = "resume_program"
SERVICE_SELECT_PROGRAM = "select_program"
SERVICE_SET_PROGRAM_AND_OPTIONS = "set_program_and_options"
SERVICE_SETTING = "change_setting"
SERVICE_START_PROGRAM = "start_program"

ATTR_AFFECTS_TO = "affects_to"
ATTR_KEY = "key"
ATTR_PROGRAM = "program"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

AFFECTS_TO_ACTIVE_PROGRAM = "active_program"
AFFECTS_TO_SELECTED_PROGRAM = "selected_program"


TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program.value): cast(ProgramKey, program)
    for program in ProgramKey
    if program != ProgramKey.UNKNOWN
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}

AVAILABLE_MAPS_ENUM = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.TempMap",
        "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map1",
        "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map2",
        "ConsumerProducts.CleaningRobot.EnumType.AvailableMaps.Map3",
    )
}

CLEANING_MODE_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CleaningRobot.EnumType.CleaningModes.Silent",
        "ConsumerProducts.CleaningRobot.EnumType.CleaningModes.Standard",
        "ConsumerProducts.CleaningRobot.EnumType.CleaningModes.Power",
    )
}

BEAN_AMOUNT_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.VeryMild",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Mild",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.MildPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Normal",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.NormalPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.Strong",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.StrongPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.VeryStrong",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.VeryStrongPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.ExtraStrong",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.DoubleShot",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.DoubleShotPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.DoubleShotPlusPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.TripleShot",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.TripleShotPlus",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanAmount.CoffeeGround",
    )
}

COFFEE_TEMPERATURE_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.88C",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.90C",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.92C",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.94C",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.95C",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeTemperature.96C",
    )
}

BEAN_CONTAINER_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.BeanContainerSelection.Right",
        "ConsumerProducts.CoffeeMaker.EnumType.BeanContainerSelection.Left",
    )
}

FLOW_RATE_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.FlowRate.Normal",
        "ConsumerProducts.CoffeeMaker.EnumType.FlowRate.Intense",
        "ConsumerProducts.CoffeeMaker.EnumType.FlowRate.IntensePlus",
    )
}

COFFEE_MILK_RATIO_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.10Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.20Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.25Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.30Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.40Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.50Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.55Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.60Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.65Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.67Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.70Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.75Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.80Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.85Percent",
        "ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.90Percent",
    )
}

HOT_WATER_TEMPERATURE_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.WhiteTea",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.GreenTea",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.BlackTea",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.50C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.55C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.60C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.65C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.70C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.75C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.80C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.85C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.90C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.95C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.97C",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.122F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.131F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.140F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.149F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.158F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.167F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.176F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.185F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.194F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.203F",
        "ConsumerProducts.CoffeeMaker.EnumType.HotWaterTemperature.Max",
    )
}

DRYING_TARGET_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "LaundryCare.Dryer.EnumType.DryingTarget.IronDry",
        "LaundryCare.Dryer.EnumType.DryingTarget.GentleDry",
        "LaundryCare.Dryer.EnumType.DryingTarget.CupboardDry",
        "LaundryCare.Dryer.EnumType.DryingTarget.CupboardDryPlus",
        "LaundryCare.Dryer.EnumType.DryingTarget.ExtraDry",
    )
}

VENTING_LEVEL_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "Cooking.Hood.EnumType.Stage.FanOff",
        "Cooking.Hood.EnumType.Stage.FanStage01",
        "Cooking.Hood.EnumType.Stage.FanStage02",
        "Cooking.Hood.EnumType.Stage.FanStage03",
        "Cooking.Hood.EnumType.Stage.FanStage04",
        "Cooking.Hood.EnumType.Stage.FanStage05",
    )
}

INTENSIVE_LEVEL_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "Cooking.Hood.EnumType.IntensiveStage.IntensiveStageOff",
        "Cooking.Hood.EnumType.IntensiveStage.IntensiveStage1",
        "Cooking.Hood.EnumType.IntensiveStage.IntensiveStage2",
    )
}

WARMING_LEVEL_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "Cooking.Oven.EnumType.WarmingLevel.Low",
        "Cooking.Oven.EnumType.WarmingLevel.Medium",
        "Cooking.Oven.EnumType.WarmingLevel.High",
    )
}

TEMPERATURE_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "LaundryCare.Washer.EnumType.Temperature.Cold",
        "LaundryCare.Washer.EnumType.Temperature.GC20",
        "LaundryCare.Washer.EnumType.Temperature.GC30",
        "LaundryCare.Washer.EnumType.Temperature.GC40",
        "LaundryCare.Washer.EnumType.Temperature.GC50",
        "LaundryCare.Washer.EnumType.Temperature.GC60",
        "LaundryCare.Washer.EnumType.Temperature.GC70",
        "LaundryCare.Washer.EnumType.Temperature.GC80",
        "LaundryCare.Washer.EnumType.Temperature.GC90",
        "LaundryCare.Washer.EnumType.Temperature.UlCold",
        "LaundryCare.Washer.EnumType.Temperature.UlWarm",
        "LaundryCare.Washer.EnumType.Temperature.UlHot",
        "LaundryCare.Washer.EnumType.Temperature.UlExtraHot",
    )
}

SPIN_SPEED_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "LaundryCare.Washer.EnumType.SpinSpeed.Off",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM400",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM600",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM700",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM800",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM900",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM1000",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM1200",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM1400",
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM1600",
        "LaundryCare.Washer.EnumType.SpinSpeed.UlOff",
        "LaundryCare.Washer.EnumType.SpinSpeed.UlLow",
        "LaundryCare.Washer.EnumType.SpinSpeed.UlMedium",
        "LaundryCare.Washer.EnumType.SpinSpeed.UlHigh",
    )
}

VARIO_PERFECT_OPTIONS = {
    bsh_key_to_translation_key(option): option
    for option in (
        "LaundryCare.Common.EnumType.VarioPerfect.Off",
        "LaundryCare.Common.EnumType.VarioPerfect.EcoPerfect",
        "LaundryCare.Common.EnumType.VarioPerfect.SpeedPerfect",
    )
}


PROGRAM_ENUM_OPTIONS = {
    bsh_key_to_translation_key(option_key): (
        option_key,
        options,
    )
    for option_key, options in (
        (
            OptionKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_REFERENCE_MAP_ID,
            AVAILABLE_MAPS_ENUM,
        ),
        (
            OptionKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_CLEANING_MODE,
            CLEANING_MODE_OPTIONS,
        ),
        (OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEAN_AMOUNT, BEAN_AMOUNT_OPTIONS),
        (
            OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_COFFEE_TEMPERATURE,
            COFFEE_TEMPERATURE_OPTIONS,
        ),
        (
            OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEAN_CONTAINER_SELECTION,
            BEAN_CONTAINER_OPTIONS,
        ),
        (OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_FLOW_RATE, FLOW_RATE_OPTIONS),
        (
            OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_COFFEE_MILK_RATIO,
            COFFEE_MILK_RATIO_OPTIONS,
        ),
        (
            OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_HOT_WATER_TEMPERATURE,
            HOT_WATER_TEMPERATURE_OPTIONS,
        ),
        (OptionKey.LAUNDRY_CARE_DRYER_DRYING_TARGET, DRYING_TARGET_OPTIONS),
        (OptionKey.COOKING_COMMON_HOOD_VENTING_LEVEL, VENTING_LEVEL_OPTIONS),
        (OptionKey.COOKING_COMMON_HOOD_INTENSIVE_LEVEL, INTENSIVE_LEVEL_OPTIONS),
        (OptionKey.COOKING_OVEN_WARMING_LEVEL, WARMING_LEVEL_OPTIONS),
        (OptionKey.LAUNDRY_CARE_WASHER_TEMPERATURE, TEMPERATURE_OPTIONS),
        (OptionKey.LAUNDRY_CARE_WASHER_SPIN_SPEED, SPIN_SPEED_OPTIONS),
        (OptionKey.LAUNDRY_CARE_COMMON_VARIO_PERFECT, VARIO_PERFECT_OPTIONS),
    )
}


OLD_NEW_UNIQUE_ID_SUFFIX_MAP = {
    "ChildLock": SettingKey.BSH_COMMON_CHILD_LOCK,
    "Operation State": StatusKey.BSH_COMMON_OPERATION_STATE,
    "Light": SettingKey.COOKING_COMMON_LIGHTING,
    "AmbientLight": SettingKey.BSH_COMMON_AMBIENT_LIGHT_ENABLED,
    "Power": SettingKey.BSH_COMMON_POWER_STATE,
    "Remaining Program Time": EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME,
    "Duration": EventKey.BSH_COMMON_OPTION_DURATION,
    "Program Progress": EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS,
    "Remote Control": StatusKey.BSH_COMMON_REMOTE_CONTROL_ACTIVE,
    "Remote Start": StatusKey.BSH_COMMON_REMOTE_CONTROL_START_ALLOWED,
    "Supermode Freezer": SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_FREEZER,
    "Supermode Refrigerator": SettingKey.REFRIGERATION_FRIDGE_FREEZER_SUPER_MODE_REFRIGERATOR,
    "Dispenser Enabled": SettingKey.REFRIGERATION_COMMON_DISPENSER_ENABLED,
    "Internal Light": SettingKey.REFRIGERATION_COMMON_LIGHT_INTERNAL_POWER,
    "External Light": SettingKey.REFRIGERATION_COMMON_LIGHT_EXTERNAL_POWER,
    "Chiller Door": StatusKey.REFRIGERATION_COMMON_DOOR_CHILLER,
    "Freezer Door": StatusKey.REFRIGERATION_COMMON_DOOR_FREEZER,
    "Refrigerator Door": StatusKey.REFRIGERATION_COMMON_DOOR_REFRIGERATOR,
    "Door Alarm Freezer": EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
    "Door Alarm Refrigerator": EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_REFRIGERATOR,
    "Temperature Alarm Freezer": EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_TEMPERATURE_ALARM_FREEZER,
    "Bean Container Empty": EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
    "Water Tank Empty": EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_WATER_TANK_EMPTY,
    "Drip Tray Full": EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DRIP_TRAY_FULL,
}

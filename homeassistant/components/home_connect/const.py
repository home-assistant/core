"""Constants for the Home Connect integration."""

import re

DOMAIN = "home_connect"

OAUTH2_AUTHORIZE = "https://api.home-connect.com/security/oauth/authorize"
OAUTH2_TOKEN = "https://api.home-connect.com/security/oauth/token"

BSH_POWER_STATE = "BSH.Common.Setting.PowerState"
BSH_POWER_ON = "BSH.Common.EnumType.PowerState.On"
BSH_POWER_OFF = "BSH.Common.EnumType.PowerState.Off"
BSH_POWER_STANDBY = "BSH.Common.EnumType.PowerState.Standby"
BSH_ACTIVE_PROGRAM = "BSH.Common.Root.ActiveProgram"
BSH_REMOTE_CONTROL_ACTIVATION_STATE = "BSH.Common.Status.RemoteControlActive"
BSH_REMOTE_START_ALLOWANCE_STATE = "BSH.Common.Status.RemoteControlStartAllowed"
BSH_CHILD_LOCK_STATE = "BSH.Common.Setting.ChildLock"

BSH_REMAINING_PROGRAM_TIME = "BSH.Common.Option.RemainingProgramTime"
BSH_COMMON_OPTION_DURATION = "BSH.Common.Option.Duration"
BSH_COMMON_OPTION_PROGRAM_PROGRESS = "BSH.Common.Option.ProgramProgress"

BSH_EVENT_PRESENT_STATE_PRESENT = "BSH.Common.EnumType.EventPresentState.Present"
BSH_EVENT_PRESENT_STATE_CONFIRMED = "BSH.Common.EnumType.EventPresentState.Confirmed"
BSH_EVENT_PRESENT_STATE_OFF = "BSH.Common.EnumType.EventPresentState.Off"

BSH_OPERATION_STATE = "BSH.Common.Status.OperationState"
BSH_OPERATION_STATE_RUN = "BSH.Common.EnumType.OperationState.Run"
BSH_OPERATION_STATE_PAUSE = "BSH.Common.EnumType.OperationState.Pause"
BSH_OPERATION_STATE_FINISHED = "BSH.Common.EnumType.OperationState.Finished"

COOKING_LIGHTING = "Cooking.Common.Setting.Lighting"
COOKING_LIGHTING_BRIGHTNESS = "Cooking.Common.Setting.LightingBrightness"

COFFEE_EVENT_BEAN_CONTAINER_EMPTY = (
    "ConsumerProducts.CoffeeMaker.Event.BeanContainerEmpty"
)
COFFEE_EVENT_WATER_TANK_EMPTY = "ConsumerProducts.CoffeeMaker.Event.WaterTankEmpty"
COFFEE_EVENT_DRIP_TRAY_FULL = "ConsumerProducts.CoffeeMaker.Event.DripTrayFull"

DISHWASHER_EVENT_SALT_NEARLY_EMPTY = "Dishcare.Dishwasher.Event.SaltNearlyEmpty"
DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY = (
    "Dishcare.Dishwasher.Event.RinseAidNearlyEmpty"
)

REFRIGERATION_INTERNAL_LIGHT_POWER = "Refrigeration.Common.Setting.Light.Internal.Power"
REFRIGERATION_INTERNAL_LIGHT_BRIGHTNESS = (
    "Refrigeration.Common.Setting.Light.Internal.Brightness"
)
REFRIGERATION_EXTERNAL_LIGHT_POWER = "Refrigeration.Common.Setting.Light.External.Power"
REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS = (
    "Refrigeration.Common.Setting.Light.External.Brightness"
)

REFRIGERATION_SUPERMODEFREEZER = "Refrigeration.FridgeFreezer.Setting.SuperModeFreezer"
REFRIGERATION_SUPERMODEREFRIGERATOR = (
    "Refrigeration.FridgeFreezer.Setting.SuperModeRefrigerator"
)
REFRIGERATION_DISPENSER = "Refrigeration.Common.Setting.Dispenser.Enabled"

REFRIGERATION_STATUS_DOOR_CHILLER = "Refrigeration.Common.Status.Door.ChillerCommon"
REFRIGERATION_STATUS_DOOR_FREEZER = "Refrigeration.Common.Status.Door.Freezer"
REFRIGERATION_STATUS_DOOR_REFRIGERATOR = "Refrigeration.Common.Status.Door.Refrigerator"

REFRIGERATION_STATUS_DOOR_CLOSED = "Refrigeration.Common.EnumType.Door.States.Closed"
REFRIGERATION_STATUS_DOOR_OPEN = "Refrigeration.Common.EnumType.Door.States.Open"

REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR = (
    "Refrigeration.FridgeFreezer.Event.DoorAlarmRefrigerator"
)
REFRIGERATION_EVENT_DOOR_ALARM_FREEZER = (
    "Refrigeration.FridgeFreezer.Event.DoorAlarmFreezer"
)
REFRIGERATION_EVENT_TEMP_ALARM_FREEZER = (
    "Refrigeration.FridgeFreezer.Event.TemperatureAlarmFreezer"
)


BSH_AMBIENT_LIGHT_ENABLED = "BSH.Common.Setting.AmbientLightEnabled"
BSH_AMBIENT_LIGHT_BRIGHTNESS = "BSH.Common.Setting.AmbientLightBrightness"
BSH_AMBIENT_LIGHT_COLOR = "BSH.Common.Setting.AmbientLightColor"
BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR = (
    "BSH.Common.EnumType.AmbientLightColor.CustomColor"
)
BSH_AMBIENT_LIGHT_CUSTOM_COLOR = "BSH.Common.Setting.AmbientLightCustomColor"

BSH_DOOR_STATE = "BSH.Common.Status.DoorState"
BSH_DOOR_STATE_CLOSED = "BSH.Common.EnumType.DoorState.Closed"
BSH_DOOR_STATE_LOCKED = "BSH.Common.EnumType.DoorState.Locked"
BSH_DOOR_STATE_OPEN = "BSH.Common.EnumType.DoorState.Open"

BSH_PAUSE = "BSH.Common.Command.PauseProgram"
BSH_RESUME = "BSH.Common.Command.ResumeProgram"

SIGNAL_UPDATE_ENTITIES = "home_connect.update_entities"

SERVICE_OPTION_ACTIVE = "set_option_active"
SERVICE_OPTION_SELECTED = "set_option_selected"
SERVICE_PAUSE_PROGRAM = "pause_program"
SERVICE_RESUME_PROGRAM = "resume_program"
SERVICE_SELECT_PROGRAM = "select_program"
SERVICE_SETTING = "change_setting"
SERVICE_START_PROGRAM = "start_program"

ATTR_ALLOWED_VALUES = "allowedvalues"
ATTR_AMBIENT = "ambient"
ATTR_BSH_KEY = "bsh_key"
ATTR_CONSTRAINTS = "constraints"
ATTR_DESC = "desc"
ATTR_DEVICE = "device"
ATTR_KEY = "key"
ATTR_PROGRAM = "program"
ATTR_SENSOR_TYPE = "sensor_type"
ATTR_SIGN = "sign"
ATTR_STEPSIZE = "stepsize"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME = "appliance_name"
SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID = "entity_id"
SVE_TRANSLATION_PLACEHOLDER_PROGRAM = "program"
SVE_TRANSLATION_PLACEHOLDER_SETTING_KEY = "setting_key"
SVE_TRANSLATION_PLACEHOLDER_VALUE = "value"

RE_CAMEL_CASE = re.compile(r"(?<!^)(?=[A-Z])")


def bsh_key_to_translation_key(bsh_key: str) -> str:
    """Convert a BSH key to a translation key format.

    This function takes a BSH key, such as `Dishcare.Dishwasher.Program.Eco50`,
    and converts it to a translation key format, such as `dishcare_dishwasher_bsh_key_eco50`.
    """
    return "_".join(
        RE_CAMEL_CASE.sub("_", split) for split in bsh_key.split(".")
    ).lower()


TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program): program
    for program in (
        "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanAll",
        "ConsumerProducts.CleaningRobot.Program.Cleaning.CleanMap",
        "ConsumerProducts.CleaningRobot.Program.Basic.GoHome",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Ristretto",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Espresso",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoDoppio",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Coffee",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.XLCoffee",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeGrande",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.EspressoMacchiato",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.Cappuccino",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.LatteMacchiato",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.CaffeLatte",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.MilkFroth",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.WarmMilk",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KleinerBrauner",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.GrosserBrauner",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Verlaengerter",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.VerlaengerterBraun",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.WienerMelange",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.FlatWhite",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Cortado",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeCortado",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeConLeche",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.CafeAuLait",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Doppio",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Kaapi",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.KoffieVerkeerd",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Galao",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Garoto",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.Americano",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.RedEye",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.BlackEye",
        "ConsumerProducts.CoffeeMaker.Program.CoffeeWorld.DeadEye",
        "ConsumerProducts.CoffeeMaker.Program.Beverage.HotWater",
        "Dishcare.Dishwasher.Program.PreRinse",
        "Dishcare.Dishwasher.Program.Auto1",
        "Dishcare.Dishwasher.Program.Auto2",
        "Dishcare.Dishwasher.Program.Auto3",
        "Dishcare.Dishwasher.Program.Eco50",
        "Dishcare.Dishwasher.Program.Quick45",
        "Dishcare.Dishwasher.Program.Intensiv70",
        "Dishcare.Dishwasher.Program.Normal65",
        "Dishcare.Dishwasher.Program.Glas40",
        "Dishcare.Dishwasher.Program.GlassCare",
        "Dishcare.Dishwasher.Program.NightWash",
        "Dishcare.Dishwasher.Program.Quick65",
        "Dishcare.Dishwasher.Program.Normal45",
        "Dishcare.Dishwasher.Program.Intensiv45",
        "Dishcare.Dishwasher.Program.AutoHalfLoad",
        "Dishcare.Dishwasher.Program.IntensivPower",
        "Dishcare.Dishwasher.Program.MagicDaily",
        "Dishcare.Dishwasher.Program.Super60",
        "Dishcare.Dishwasher.Program.Kurz60",
        "Dishcare.Dishwasher.Program.ExpressSparkle65",
        "Dishcare.Dishwasher.Program.MachineCare",
        "Dishcare.Dishwasher.Program.SteamFresh",
        "Dishcare.Dishwasher.Program.MaximumCleaning",
        "Dishcare.Dishwasher.Program.MixedLoad",
        "LaundryCare.Dryer.Program.Cotton",
        "LaundryCare.Dryer.Program.Synthetic",
        "LaundryCare.Dryer.Program.Mix",
        "LaundryCare.Dryer.Program.Blankets",
        "LaundryCare.Dryer.Program.BusinessShirts",
        "LaundryCare.Dryer.Program.DownFeathers",
        "LaundryCare.Dryer.Program.Hygiene",
        "LaundryCare.Dryer.Program.Jeans",
        "LaundryCare.Dryer.Program.Outdoor",
        "LaundryCare.Dryer.Program.SyntheticRefresh",
        "LaundryCare.Dryer.Program.Towels",
        "LaundryCare.Dryer.Program.Delicates",
        "LaundryCare.Dryer.Program.Super40",
        "LaundryCare.Dryer.Program.Shirts15",
        "LaundryCare.Dryer.Program.Pillow",
        "LaundryCare.Dryer.Program.AntiShrink",
        "LaundryCare.Dryer.Program.MyTime.MyDryingTime",
        "LaundryCare.Dryer.Program.TimeCold",
        "LaundryCare.Dryer.Program.TimeWarm",
        "LaundryCare.Dryer.Program.InBasket",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold20",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold30",
        "LaundryCare.Dryer.Program.TimeColdFix.TimeCold60",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm30",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm40",
        "LaundryCare.Dryer.Program.TimeWarmFix.TimeWarm60",
        "LaundryCare.Dryer.Program.Dessous",
        "Cooking.Common.Program.Hood.Automatic",
        "Cooking.Common.Program.Hood.Venting",
        "Cooking.Common.Program.Hood.DelayedShutOff",
        "Cooking.Oven.Program.HeatingMode.PreHeating",
        "Cooking.Oven.Program.HeatingMode.HotAir",
        "Cooking.Oven.Program.HeatingMode.HotAirEco",
        "Cooking.Oven.Program.HeatingMode.HotAirGrilling",
        "Cooking.Oven.Program.HeatingMode.TopBottomHeating",
        "Cooking.Oven.Program.HeatingMode.TopBottomHeatingEco",
        "Cooking.Oven.Program.HeatingMode.BottomHeating",
        "Cooking.Oven.Program.HeatingMode.PizzaSetting",
        "Cooking.Oven.Program.HeatingMode.SlowCook",
        "Cooking.Oven.Program.HeatingMode.IntensiveHeat",
        "Cooking.Oven.Program.HeatingMode.KeepWarm",
        "Cooking.Oven.Program.HeatingMode.PreheatOvenware",
        "Cooking.Oven.Program.HeatingMode.FrozenHeatupSpecial",
        "Cooking.Oven.Program.HeatingMode.Desiccation",
        "Cooking.Oven.Program.HeatingMode.Defrost",
        "Cooking.Oven.Program.HeatingMode.Proof",
        "Cooking.Oven.Program.HeatingMode.HotAir30Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir60Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir80Steam",
        "Cooking.Oven.Program.HeatingMode.HotAir100Steam",
        "Cooking.Oven.Program.HeatingMode.SabbathProgramme",
        "Cooking.Oven.Program.Microwave90Watt",
        "Cooking.Oven.Program.Microwave180Watt",
        "Cooking.Oven.Program.Microwave360Watt",
        "Cooking.Oven.Program.Microwave600Watt",
        "Cooking.Oven.Program.Microwave900Watt",
        "Cooking.Oven.Program.Microwave1000Watt",
        "Cooking.Oven.Program.Microwave.Max",
        "Cooking.Oven.Program.HeatingMode.WarmingDrawer",
        "LaundryCare.Washer.Program.Cotton",
        "LaundryCare.Washer.Program.Cotton.CottonEco",
        "LaundryCare.Washer.Program.Cotton.Eco4060",
        "LaundryCare.Washer.Program.Cotton.Colour",
        "LaundryCare.Washer.Program.EasyCare",
        "LaundryCare.Washer.Program.Mix",
        "LaundryCare.Washer.Program.Mix.NightWash",
        "LaundryCare.Washer.Program.DelicatesSilk",
        "LaundryCare.Washer.Program.Wool",
        "LaundryCare.Washer.Program.Sensitive",
        "LaundryCare.Washer.Program.Auto30",
        "LaundryCare.Washer.Program.Auto40",
        "LaundryCare.Washer.Program.Auto60",
        "LaundryCare.Washer.Program.Chiffon",
        "LaundryCare.Washer.Program.Curtains",
        "LaundryCare.Washer.Program.DarkWash",
        "LaundryCare.Washer.Program.Dessous",
        "LaundryCare.Washer.Program.Monsoon",
        "LaundryCare.Washer.Program.Outdoor",
        "LaundryCare.Washer.Program.PlushToy",
        "LaundryCare.Washer.Program.ShirtsBlouses",
        "LaundryCare.Washer.Program.SportFitness",
        "LaundryCare.Washer.Program.Towels",
        "LaundryCare.Washer.Program.WaterProof",
        "LaundryCare.Washer.Program.PowerSpeed59",
        "LaundryCare.Washer.Program.Super153045.Super15",
        "LaundryCare.Washer.Program.Super153045.Super1530",
        "LaundryCare.Washer.Program.DownDuvet.Duvet",
        "LaundryCare.Washer.Program.Rinse.RinseSpinDrain",
        "LaundryCare.Washer.Program.DrumClean",
        "LaundryCare.WasherDryer.Program.Cotton",
        "LaundryCare.WasherDryer.Program.Cotton.Eco4060",
        "LaundryCare.WasherDryer.Program.Mix",
        "LaundryCare.WasherDryer.Program.EasyCare",
        "LaundryCare.WasherDryer.Program.WashAndDry60",
        "LaundryCare.WasherDryer.Program.WashAndDry90",
    )
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}

REFERENCE_MAP_ID_OPTIONS = {
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
        "LaundryCare.Washer.EnumType.SpinSpeed.RPM800",
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


PROGRAM_ENUM_OPTIONS: dict[str, dict[str, str | dict[str, str]]] = {
    bsh_key_to_translation_key(option_key): {
        ATTR_BSH_KEY: option_key,
        ATTR_ALLOWED_VALUES: options,
    }
    for option_key, options in (
        (
            "ConsumerProducts.CleaningRobot.Option.ReferenceMapId",
            REFERENCE_MAP_ID_OPTIONS,
        ),
        ("ConsumerProducts.CleaningRobot.Option.CleaningMode", CLEANING_MODE_OPTIONS),
        ("ConsumerProducts.CoffeeMaker.Option.BeanAmount", BEAN_AMOUNT_OPTIONS),
        (
            "ConsumerProducts.CoffeeMaker.Option.CoffeeTemperature",
            COFFEE_TEMPERATURE_OPTIONS,
        ),
        ("ConsumerProducts.CoffeeMaker.Option.BeanContainer", BEAN_CONTAINER_OPTIONS),
        ("ConsumerProducts.CoffeeMaker.Option.FlowRate", FLOW_RATE_OPTIONS),
        (
            "ConsumerProducts.CoffeeMaker.Option.HotWaterTemperature",
            HOT_WATER_TEMPERATURE_OPTIONS,
        ),
        ("LaundryCare.Dryer.Option.DryingTarget", DRYING_TARGET_OPTIONS),
        ("Cooking.Hood.Option.VentingLevel", VENTING_LEVEL_OPTIONS),
        ("Cooking.Hood.Option.IntensiveLevel", INTENSIVE_LEVEL_OPTIONS),
        ("Cooking.Oven.Option.WarmingLevel", WARMING_LEVEL_OPTIONS),
        ("LaundryCare.Washer.Option.Temperature", TEMPERATURE_OPTIONS),
        ("LaundryCare.Washer.Option.SpinSpeed", SPIN_SPEED_OPTIONS),
        ("LaundryCare.Washer.Option.VarioPerfect", VARIO_PERFECT_OPTIONS),
    )
}

OLD_NEW_UNIQUE_ID_SUFFIX_MAP = {
    "ChildLock": BSH_CHILD_LOCK_STATE,
    "Operation State": BSH_OPERATION_STATE,
    "Light": COOKING_LIGHTING,
    "AmbientLight": BSH_AMBIENT_LIGHT_ENABLED,
    "Power": BSH_POWER_STATE,
    "Remaining Program Time": BSH_REMAINING_PROGRAM_TIME,
    "Duration": BSH_COMMON_OPTION_DURATION,
    "Program Progress": BSH_COMMON_OPTION_PROGRAM_PROGRESS,
    "Remote Control": BSH_REMOTE_CONTROL_ACTIVATION_STATE,
    "Remote Start": BSH_REMOTE_START_ALLOWANCE_STATE,
    "Supermode Freezer": REFRIGERATION_SUPERMODEFREEZER,
    "Supermode Refrigerator": REFRIGERATION_SUPERMODEREFRIGERATOR,
    "Dispenser Enabled": REFRIGERATION_DISPENSER,
    "Internal Light": REFRIGERATION_INTERNAL_LIGHT_POWER,
    "External Light": REFRIGERATION_EXTERNAL_LIGHT_POWER,
    "Chiller Door": REFRIGERATION_STATUS_DOOR_CHILLER,
    "Freezer Door": REFRIGERATION_STATUS_DOOR_FREEZER,
    "Refrigerator Door": REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
    "Door Alarm Freezer": REFRIGERATION_EVENT_DOOR_ALARM_FREEZER,
    "Door Alarm Refrigerator": REFRIGERATION_EVENT_DOOR_ALARM_REFRIGERATOR,
    "Temperature Alarm Freezer": REFRIGERATION_EVENT_TEMP_ALARM_FREEZER,
    "Bean Container Empty": COFFEE_EVENT_BEAN_CONTAINER_EMPTY,
    "Water Tank Empty": COFFEE_EVENT_WATER_TANK_EMPTY,
    "Drip Tray Full": COFFEE_EVENT_DRIP_TRAY_FULL,
}

"""Constants for the Home Connect integration."""

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

ATTR_AMBIENT = "ambient"
ATTR_BSH_KEY = "bsh_key"
ATTR_DESC = "desc"
ATTR_DEVICE = "device"
ATTR_KEY = "key"
ATTR_PROGRAM = "program"
ATTR_SENSOR_TYPE = "sensor_type"
ATTR_SIGN = "sign"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"

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

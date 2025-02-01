"""Constants for the Home Connect integration."""

from aiohomeconnect.model import EventKey, SettingKey, StatusKey

DOMAIN = "home_connect"


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
SERVICE_SETTING = "change_setting"
SERVICE_START_PROGRAM = "start_program"


ATTR_KEY = "key"
ATTR_PROGRAM = "program"
ATTR_UNIT = "unit"
ATTR_VALUE = "value"


SVE_TRANSLATION_KEY_SET_SETTING = "set_setting_entity"
SVE_TRANSLATION_PLACEHOLDER_APPLIANCE_NAME = "appliance_name"
SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID = "entity_id"
SVE_TRANSLATION_PLACEHOLDER_PROGRAM = "program"
SVE_TRANSLATION_PLACEHOLDER_KEY = "key"
SVE_TRANSLATION_PLACEHOLDER_VALUE = "value"


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

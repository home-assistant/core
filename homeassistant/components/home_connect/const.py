"""Constants for the Home Connect integration."""

DOMAIN = "home_connect"

OAUTH2_AUTHORIZE = "https://api.home-connect.com/security/oauth/authorize"
OAUTH2_TOKEN = "https://api.home-connect.com/security/oauth/token"

BSH_POWER_STATE = "BSH.Common.Setting.PowerState"
BSH_POWER_ON = "BSH.Common.EnumType.PowerState.On"
BSH_POWER_OFF = "BSH.Common.EnumType.PowerState.Off"
BSH_POWER_STANDBY = "BSH.Common.EnumType.PowerState.Standby"
BSH_ACTIVE_PROGRAM = "BSH.Common.Root.ActiveProgram"
BSH_OPERATION_STATE = "BSH.Common.Status.OperationState"
BSH_REMOTE_CONTROL_ACTIVATION_STATE = "BSH.Common.Status.RemoteControlActive"
BSH_REMOTE_START_ALLOWANCE_STATE = "BSH.Common.Status.RemoteControlStartAllowed"

COOKING_LIGHTING = "Cooking.Common.Setting.Lighting"
COOKING_LIGHTING_BRIGHTNESS = "Cooking.Common.Setting.LightingBrightness"

BSH_AMBIENT_LIGHT_ENABLED = "BSH.Common.Setting.AmbientLightEnabled"
BSH_AMBIENT_LIGHT_BRIGHTNESS = "BSH.Common.Setting.AmbientLightBrightness"
BSH_AMBIENT_LIGHT_COLOR = "BSH.Common.Setting.AmbientLightColor"
BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR = (
    "BSH.Common.EnumType.AmbientLightColor.CustomColor"
)
BSH_AMBIENT_LIGHT_CUSTOM_COLOR = "BSH.Common.Setting.AmbientLightCustomColor"

BSH_DOOR_STATE = "BSH.Common.Status.DoorState"

SIGNAL_UPDATE_ENTITIES = "home_connect.update_entities"

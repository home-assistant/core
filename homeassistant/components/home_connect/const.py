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

COOKING_LIGHTING = "Cooking.Common.Setting.Lighting"
COOKING_LIGHTINGBRIGHTNESS = "Cooking.Common.Setting.LightingBrightness"

BSH_AMBIENTLIGHTENABLED = "BSH.Common.Setting.AmbientLightEnabled"
BSH_AMBIENTLIGHTBRIGHTNESS = "BSH.Common.Setting.AmbientLightBrightness"
BSH_AMBIENTLIGHTCOLOR = "BSH.Common.Setting.AmbientLightColor"
BSH_AMBIENTLIGHTCOLOR_CUSTOMCOLOR = "BSH.Common.EnumType.AmbientLightColor.CustomColor"
BSH_AMBIENTLIGHTCUSTOMCOLOR = "BSH.Common.Setting.AmbientLightCustomColor"

BSH_DOOR_STATE = "BSH.Common.Status.DoorState"
BSH_PAUSE = "BSH.Common.Command.PauseProgram"
BSH_RESUME = "BSH.Common.Command.ResumeProgram"

SIGNAL_UPDATE_ENTITIES = "home_connect.update_entities"

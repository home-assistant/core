"""Constants for the Hue component."""
from aiohue.v2.models.button import ButtonEvent
from aiohue.v2.models.relative_rotary import (
    RelativeRotaryAction,
    RelativeRotaryDirection,
)

DOMAIN = "hue"

CONF_API_VERSION = "api_version"
CONF_IGNORE_AVAILABILITY = "ignore_availability"

CONF_SUBTYPE = "subtype"

ATTR_HUE_EVENT = "hue_event"
SERVICE_HUE_ACTIVATE_SCENE = "hue_activate_scene"
ATTR_GROUP_NAME = "group_name"
ATTR_SCENE_NAME = "scene_name"
ATTR_TRANSITION = "transition"
ATTR_DYNAMIC = "dynamic"


# V1 API SPECIFIC CONSTANTS ##################

GROUP_TYPE_LIGHT_GROUP = "LightGroup"
GROUP_TYPE_ROOM = "Room"
GROUP_TYPE_LUMINAIRE = "Luminaire"
GROUP_TYPE_LIGHT_SOURCE = "LightSource"
GROUP_TYPE_ZONE = "Zone"
GROUP_TYPE_ENTERTAINMENT = "Entertainment"

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = False

CONF_ALLOW_UNREACHABLE = "allow_unreachable"
DEFAULT_ALLOW_UNREACHABLE = False

# How long to wait to actually do the refresh after requesting it.
# We wait some time so if we control multiple lights, we batch requests.
REQUEST_REFRESH_DELAY = 0.3


# V2 API SPECIFIC CONSTANTS ##################

DEFAULT_BUTTON_EVENT_TYPES = (
    # I have never ever seen the `DOUBLE_SHORT_RELEASE`
    # or `DOUBLE_SHORT_RELEASE` events so leave them out here
    ButtonEvent.INITIAL_PRESS,
    ButtonEvent.REPEAT,
    ButtonEvent.SHORT_RELEASE,
    ButtonEvent.LONG_RELEASE,
)

DEFAULT_ROTARY_EVENT_TYPES = (RelativeRotaryAction.START, RelativeRotaryAction.REPEAT)
DEFAULT_ROTARY_EVENT_SUBTYPES = (
    RelativeRotaryDirection.CLOCK_WISE,
    RelativeRotaryDirection.COUNTER_CLOCK_WISE,
)

DEVICE_SPECIFIC_EVENT_TYPES = {
    # device specific overrides of specific supported button events
    "Hue tap switch": (ButtonEvent.INITIAL_PRESS,),
}

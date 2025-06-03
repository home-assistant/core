"""smarttub constants."""

DOMAIN = "smarttub"

EVENT_SMARTTUB = "smarttub"

SCAN_INTERVAL = 60

POLLING_TIMEOUT = 10
API_TIMEOUT = 5

DEFAULT_MIN_TEMP = 18.5
DEFAULT_MAX_TEMP = 40

# the device doesn't remember any state for the light, so we have to choose a
# mode (smarttub.SpaLight.LightMode) when turning it on. There is no white
# mode.
DEFAULT_LIGHT_EFFECT = "purple"
# default to 50% brightness
DEFAULT_LIGHT_BRIGHTNESS = 128

ATTR_ERRORS = "errors"
ATTR_LIGHTS = "lights"
ATTR_PUMPS = "pumps"
ATTR_REMINDERS = "reminders"
ATTR_STATUS = "status"

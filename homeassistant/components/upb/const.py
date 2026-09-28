"""Support the UPB PIM."""

import probatio

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

DOMAIN = "upb"

ATTR_ADDRESS = "address"
ATTR_BLINK_RATE = "blink_rate"
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_RATE = "rate"
CONF_NETWORK = "network"
EVENT_UPB_SCENE_CHANGED = "upb.scene_changed"

VALID_BRIGHTNESS = probatio.All(probatio.Coerce(int), probatio.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = probatio.All(
    probatio.Coerce(float), probatio.Range(min=0, max=100)
)
VALID_RATE = probatio.All(probatio.Coerce(float), probatio.Clamp(min=-1, max=3600))

UPB_BRIGHTNESS_RATE_SCHEMA = probatio.All(
    cv.has_at_least_one_key(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT),
    cv.make_entity_service_schema(
        {
            probatio.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
            probatio.Exclusive(
                ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS
            ): VALID_BRIGHTNESS_PCT,
            probatio.Optional(ATTR_RATE, default=-1): VALID_RATE,
        }
    ),
)

UPB_BLINK_RATE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_BLINK_RATE, default=0.5): probatio.All(
        probatio.Coerce(float), probatio.Range(min=0, max=4.25)
    )
}

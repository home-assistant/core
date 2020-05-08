"""Support the UPB PIM."""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

CONF_NETWORK = "network"
DOMAIN = "upb"

ATTR_BLINK_RATE = "blink_rate"
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_RATE = "rate"
VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
VALID_RATE = vol.All(vol.Coerce(float), vol.Clamp(min=-1, max=3600))

UPB_BRIGHTNESS_RATE_SCHEMA = vol.All(
    cv.has_at_least_one_key(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT),
    cv.make_entity_service_schema(
        {
            vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
            vol.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
            vol.Optional(ATTR_RATE, default=-1): VALID_RATE,
        }
    ),
)

UPB_BLINK_RATE_SCHEMA = {
    vol.Required(ATTR_BLINK_RATE, default=0.5): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=4.25)
    )
}

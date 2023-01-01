"""Helpers for philips_js."""

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE

from .const import DOMAIN, TRIGGER_TYPE_TURN_ON


def async_get_turn_on_trigger(device_id: str) -> dict[str, str]:
    """Return trigger description for a turn on trigger."""

    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: TRIGGER_TYPE_TURN_ON,
    }

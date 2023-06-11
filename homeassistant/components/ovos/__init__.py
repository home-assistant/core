"""Support for OpenVoiceOS (OVOS) and Neon AI."""
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

DOMAIN = "ovos"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OVOS/Neon component."""
    hass.data[DOMAIN] = config[DOMAIN][CONF_HOST]
    discovery.load_platform(hass, Platform.NOTIFY, DOMAIN, {}, config)
    return True

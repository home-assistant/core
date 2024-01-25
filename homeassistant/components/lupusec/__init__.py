"""Support for Lupusec Home Security system."""
import logging

import lupupy
from lupupy.exceptions import LupusecException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lupusec"

NOTIFICATION_ID = "lupusec_notification"
NOTIFICATION_TITLE = "Lupusec Security Setup"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Optional(CONF_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lupusec integration."""

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    conf[CONF_HOST] = conf[CONF_IP_ADDRESS]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        lupusec_system = await hass.async_add_executor_job(
            LupusecSystem,
            username,
            password,
            host,
        )
    except LupusecException:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        return False
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error(
            "Unknown error while trying to connect to Lupusec device at %s: %s",
            host,
            ex,
        )
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = lupusec_system

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class LupusecSystem:
    """Lupusec System class."""

    def __init__(self, username, password, ip_address) -> None:
        """Initialize the system."""
        self.lupusec = lupupy.Lupusec(username, password, ip_address)


class LupusecDevice(Entity):
    """Representation of a Lupusec device."""

    def __init__(self, data, device, config_entry=None) -> None:
        """Initialize a sensor for Lupusec device."""
        self._data = data
        self._device = device
        self._entry_id = config_entry.entry_id if config_entry else "_none"

    def update(self):
        """Update automation state."""
        self._device.refresh()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device.name

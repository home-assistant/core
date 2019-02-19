"""Support for Toon van Eneco devices."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import config_flow  # noqa  pylint_disable=unused-import
from .const import (
    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DISPLAY, CONF_TENANT,
    DATA_TOON_CLIENT, DATA_TOON_CONFIG, DOMAIN)

REQUIREMENTS = ['toonapilib==3.0.4']

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Toon components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Store config to be used during entry setup
    hass.data[DATA_TOON_CONFIG] = conf

    return True


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigType) -> bool:
    """Set up Toon from a config entry."""
    from toonapilib import Toon

    conf = hass.data.get(DATA_TOON_CONFIG)

    toon = Toon(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
                conf[CONF_CLIENT_ID], conf[CONF_CLIENT_SECRET],
                tenant_id=entry.data[CONF_TENANT],
                display_common_name=entry.data[CONF_DISPLAY])

    hass.data.setdefault(DATA_TOON_CLIENT, {})[entry.entry_id] = toon

    for component in 'binary_sensor', 'climate', 'sensor':
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component))

    return True


class ToonEntity(Entity):
    """Defines a base Toon entity."""

    def __init__(self, toon, name: str, icon: str) -> None:
        """Initialize the Toon entity."""
        self._name = name
        self._state = None
        self._icon = icon
        self.toon = toon

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            'identifiers': {
                (DOMAIN, self.toon.agreement.id)
            }
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

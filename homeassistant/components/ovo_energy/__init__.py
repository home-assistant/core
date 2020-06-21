"""Support for OVO Energy."""
import logging
from typing import Any, Dict

import aiohttp
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.ovo_energy.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the OVO Energy components."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up OVO Energy from a config entry."""

    client = OVOEnergy()

    try:
        await client.authenticate(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    # Setup components
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload OVO Energy config entry."""
    # Unload sensors
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    del hass.data[DOMAIN][entry.entry_id]

    return True


class OVOEnergyEntity(Entity):
    """Defines a base OVO Energy entity."""

    def __init__(self, client: OVOEnergy, key: str, name: str, icon: str) -> None:
        """Initialize the OVO Energy entity."""
        self._client = client
        self._key = key
        self._name = name
        self._icon = icon
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._key

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    async def async_update(self) -> None:
        """Update OVO Energy entity."""
        if await self._ovo_energy_update():
            self._available = True
        else:
            if self._available:
                _LOGGER.debug(
                    "An error occurred while updating OVO Energy sensor.",
                    exc_info=True,
                )
            self._available = False

    async def _ovo_energy_update(self) -> None:
        """Update OVO Energy entity."""
        raise NotImplementedError()


class OVOEnergyDeviceEntity(OVOEnergyEntity):
    """Defines a OVO Energy device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this OVO Energy instance."""
        return {
            "identifiers": {(DOMAIN, self._client.account_id)},
            "manufacturer": "OVO Energy",
            "name": self._client.account_id,
        }

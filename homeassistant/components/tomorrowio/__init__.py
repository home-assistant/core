"""The Tomorrow.io integration."""

from __future__ import annotations

from pytomorrowio import TomorrowioV4
from pytomorrowio.const import CURRENT

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, INTEGRATION_NAME
from .coordinator import TomorrowioDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN, WEATHER_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tomorrow.io API from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]
    # If coordinator already exists for this API key, we'll use that, otherwise
    # we have to create a new one
    if not (coordinator := hass.data[DOMAIN].get(api_key)):
        session = async_get_clientsession(hass)
        # we will not use the class's lat and long so we can pass in garbage
        # lats and longs
        api = TomorrowioV4(api_key, 361.0, 361.0, unit_system="metric", session=session)
        coordinator = TomorrowioDataUpdateCoordinator(hass, api)
        hass.data[DOMAIN][api_key] = coordinator

    await coordinator.async_setup_entry(entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    api_key = config_entry.data[CONF_API_KEY]
    coordinator: TomorrowioDataUpdateCoordinator = hass.data[DOMAIN][api_key]
    # If this is true, we can remove the coordinator
    if await coordinator.async_unload_entry(config_entry):
        hass.data[DOMAIN].pop(api_key)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


class TomorrowioEntity(CoordinatorEntity[TomorrowioDataUpdateCoordinator]):
    """Base Tomorrow.io Entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
    ) -> None:
        """Initialize Tomorrow.io Entity."""
        super().__init__(coordinator)
        self.api_version = api_version
        self._config_entry = config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.data[CONF_API_KEY])},
            manufacturer=INTEGRATION_NAME,
            sw_version=f"v{self.api_version}",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_current_property(self, property_name: str) -> int | str | float | None:
        """Get property from current conditions.

        Used for V4 API.
        """
        entry_id = self._config_entry.entry_id
        return self.coordinator.data[entry_id].get(CURRENT, {}).get(property_name)

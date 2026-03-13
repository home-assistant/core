"""Button platform for the KWB Modbus integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KwbModbusConfigEntry
from .const import CONF_HEATING_DEVICE, DOMAIN, HEATING_DEVICES
from .coordinator import KWBDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KwbModbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KWB Modbus button entities."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    async_add_entities([KWBRediscoverButton(coordinator, entry)])


class KWBRediscoverButton(ButtonEntity):
    """Button to trigger a re-discovery of KWB sensors."""

    _attr_has_entity_name = True
    _attr_name = "Re-run Sensor Discovery"
    _attr_icon = "mdi:magnify-scan"

    def __init__(self, coordinator: KWBDataUpdateCoordinator, entry: KwbModbusConfigEntry) -> None:
        """Initialize the rediscover button."""
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rediscover"

    async def async_press(self) -> None:
        """Run sensor discovery and refresh coordinator data."""
        await self._coordinator.async_run_discovery()
        await self._coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        model = HEATING_DEVICES.get(self._entry.data.get(CONF_HEATING_DEVICE, ""), "KWB Heating")
        data = self._coordinator.data or {}
        major, minor, patch = data.get(8192), data.get(8193), data.get(8194)
        sw_version = (
            f"{major}.{minor}.{patch}" if None not in (major, minor, patch) else None
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=model,
            manufacturer="KWB",
            model=model,
            sw_version=sw_version,
        )

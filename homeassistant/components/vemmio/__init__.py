"""The Vemmio integration."""

from __future__ import annotations

from vemmio_client import Client, DeviceNode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VemmioDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vemmio from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coord = VemmioDataUpdateCoordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    await coord.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class VemmioEntity(CoordinatorEntity[VemmioDataUpdateCoordinator]):
    """Base class for Vemmio entities."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        *,
        coordinator: VemmioDataUpdateCoordinator,
        mac: str,
        typ: str,
        revision: str,
        key: str,
        node: DeviceNode,
        index: int,
    ) -> None:
        """Initialize the Vemmio entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{typ}_{key}_{index}"
        self.mac = mac
        self.typ = typ
        self.revision = revision
        self.node = node

    def client(self) -> Client:
        """Return the Vemmio client."""
        return self.coordinator.client

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""

        return DeviceInfo(
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Vemmio",
            model=self.typ.title(),
            name=self.typ.title(),
            sw_version=self.revision,
        )

"""Support for setting the Transmission BitTorrent client Turtle Mode."""
from collections.abc import Callable
import logging
from typing import Any

from transmission_rpc.session import SessionStats

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_TYPES
from .coordinator import TransmissionDataUpdateCoordinator

_LOGGING = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transmission switch."""

    coordinator: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    name: str = config_entry.data[CONF_NAME]

    dev = []
    for switch_type, switch_name in SWITCH_TYPES.items():
        dev.append(TransmissionSwitch(switch_type, switch_name, coordinator, name))

    async_add_entities(dev, True)


class TransmissionSwitch(CoordinatorEntity[SessionStats], SwitchEntity):
    """Representation of a Transmission switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        switch_type: str,
        switch_name: str,
        coordinator: TransmissionDataUpdateCoordinator,
        client_name: str,
    ) -> None:
        """Initialize the Transmission switch."""
        super().__init__(coordinator)
        self._attr_name = switch_name
        self.type = switch_type
        self.unsub_update: Callable[[], None] | None = None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{switch_type}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Transmission",
            name=client_name,
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        active = None
        if self.type == "on_off":
            active = self.coordinator.data.active_torrent_count > 0
        elif self.type == "turtle_mode":
            active = self.coordinator.api.get_alt_speed_enabled()

        return bool(active)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.type == "on_off":
            _LOGGING.debug("Starting all torrents")
            await self.hass.async_add_executor_job(self.coordinator.api.start_torrents)
        elif self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission on")
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_alt_speed_enabled, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.type == "on_off":
            _LOGGING.debug("Stopping all torrents")
            await self.hass.async_add_executor_job(self.coordinator.api.stop_torrents)
        if self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission off")
            await self.hass.async_add_executor_job(
                self.coordinator.api.set_alt_speed_enabled, False
            )
        await self.coordinator.async_request_refresh()

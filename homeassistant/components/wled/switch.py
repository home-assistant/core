"""Support for WLED switches."""
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import WLEDDataUpdateCoordinator, WLEDDeviceEntity, wled_exception_handler
from .const import (
    ATTR_DURATION,
    ATTR_FADE,
    ATTR_TARGET_BRIGHTNESS,
    ATTR_UDP_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up WLED switch based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        WLEDNightlightSwitch(entry.entry_id, coordinator),
        WLEDSyncSendSwitch(entry.entry_id, coordinator),
        WLEDSyncReceiveSwitch(entry.entry_id, coordinator),
    ]
    async_add_entities(switches, True)


class WLEDSwitch(WLEDDeviceEntity, SwitchEntity):
    """Defines a WLED switch."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: WLEDDataUpdateCoordinator,
        name: str,
        icon: str,
        key: str,
    ) -> None:
        """Initialize WLED switch."""
        self._key = key
        super().__init__(
            entry_id=entry_id, coordinator=coordinator, name=name, icon=icon
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.data.info.mac_address}_{self._key}"


class WLEDNightlightSwitch(WLEDSwitch):
    """Defines a WLED nightlight switch."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED nightlight switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:weather-night",
            key="nightlight",
            name=f"{coordinator.data.info.name} Nightlight",
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {
            ATTR_DURATION: self.coordinator.data.state.nightlight.duration,
            ATTR_FADE: self.coordinator.data.state.nightlight.fade,
            ATTR_TARGET_BRIGHTNESS: self.coordinator.data.state.nightlight.target_brightness,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.nightlight.on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED nightlight switch."""
        await self.coordinator.wled.nightlight(on=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED nightlight switch."""
        await self.coordinator.wled.nightlight(on=True)


class WLEDSyncSendSwitch(WLEDSwitch):
    """Defines a WLED sync send switch."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED sync send switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:upload-network-outline",
            key="sync_send",
            name=f"{coordinator.data.info.name} Sync Send",
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {ATTR_UDP_PORT: self.coordinator.data.info.udp_port}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.sync.send)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED sync send switch."""
        await self.coordinator.wled.sync(send=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED sync send switch."""
        await self.coordinator.wled.sync(send=True)


class WLEDSyncReceiveSwitch(WLEDSwitch):
    """Defines a WLED sync receive switch."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator):
        """Initialize WLED sync receive switch."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:download-network-outline",
            key="sync_receive",
            name=f"{coordinator.data.info.name} Sync Receive",
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {ATTR_UDP_PORT: self.coordinator.data.info.udp_port}

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return bool(self.coordinator.data.state.sync.receive)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the WLED sync receive switch."""
        await self.coordinator.wled.sync(receive=False)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the WLED sync receive switch."""
        await self.coordinator.wled.sync(receive=True)

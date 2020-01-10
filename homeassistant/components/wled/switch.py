"""Support for WLED switches."""
import logging
from typing import Any, Callable, List

from wled import WLED, WLEDError

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import WLEDDeviceEntity
from .const import (
    ATTR_DURATION,
    ATTR_FADE,
    ATTR_TARGET_BRIGHTNESS,
    ATTR_UDP_PORT,
    DATA_WLED_CLIENT,
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
    wled: WLED = hass.data[DOMAIN][entry.entry_id][DATA_WLED_CLIENT]

    switches = [
        WLEDNightlightSwitch(entry.entry_id, wled),
        WLEDSyncSendSwitch(entry.entry_id, wled),
        WLEDSyncReceiveSwitch(entry.entry_id, wled),
    ]
    async_add_entities(switches, True)


class WLEDSwitch(WLEDDeviceEntity, SwitchDevice):
    """Defines a WLED switch."""

    def __init__(
        self, entry_id: str, wled: WLED, name: str, icon: str, key: str
    ) -> None:
        """Initialize WLED switch."""
        self._key = key
        self._state = False
        super().__init__(entry_id, wled, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.wled.device.info.mac_address}_{self._key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._state

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._wled_turn_off()
            self._state = False
        except WLEDError:
            _LOGGER.error("An error occurred while turning off WLED switch.")
            self._available = False
        self.async_schedule_update_ha_state()

    async def _wled_turn_off(self) -> None:
        """Turn off the switch."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._wled_turn_on()
            self._state = True
        except WLEDError:
            _LOGGER.error("An error occurred while turning on WLED switch")
            self._available = False
        self.async_schedule_update_ha_state()

    async def _wled_turn_on(self) -> None:
        """Turn on the switch."""
        raise NotImplementedError()


class WLEDNightlightSwitch(WLEDSwitch):
    """Defines a WLED nightlight switch."""

    def __init__(self, entry_id: str, wled: WLED) -> None:
        """Initialize WLED nightlight switch."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Nightlight",
            "mdi:weather-night",
            "nightlight",
        )

    async def _wled_turn_off(self) -> None:
        """Turn off the WLED nightlight switch."""
        await self.wled.nightlight(on=False)

    async def _wled_turn_on(self) -> None:
        """Turn on the WLED nightlight switch."""
        await self.wled.nightlight(on=True)

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        self._state = self.wled.device.state.nightlight.on
        self._attributes = {
            ATTR_DURATION: self.wled.device.state.nightlight.duration,
            ATTR_FADE: self.wled.device.state.nightlight.fade,
            ATTR_TARGET_BRIGHTNESS: self.wled.device.state.nightlight.target_brightness,
        }


class WLEDSyncSendSwitch(WLEDSwitch):
    """Defines a WLED sync send switch."""

    def __init__(self, entry_id: str, wled: WLED) -> None:
        """Initialize WLED sync send switch."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Sync Send",
            "mdi:upload-network-outline",
            "sync_send",
        )

    async def _wled_turn_off(self) -> None:
        """Turn off the WLED sync send switch."""
        await self.wled.sync(send=False)

    async def _wled_turn_on(self) -> None:
        """Turn on the WLED sync send switch."""
        await self.wled.sync(send=True)

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        self._state = self.wled.device.state.sync.send
        self._attributes = {ATTR_UDP_PORT: self.wled.device.info.udp_port}


class WLEDSyncReceiveSwitch(WLEDSwitch):
    """Defines a WLED sync receive switch."""

    def __init__(self, entry_id: str, wled: WLED):
        """Initialize WLED sync receive switch."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Sync Receive",
            "mdi:download-network-outline",
            "sync_receive",
        )

    async def _wled_turn_off(self) -> None:
        """Turn off the WLED sync receive switch."""
        await self.wled.sync(receive=False)

    async def _wled_turn_on(self) -> None:
        """Turn on the WLED sync receive switch."""
        await self.wled.sync(receive=True)

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        self._state = self.wled.device.state.sync.receive
        self._attributes = {ATTR_UDP_PORT: self.wled.device.info.udp_port}

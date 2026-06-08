"""Support for Switchbot bot."""

import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, override

import switchbot

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import AIRPURIFIER_BASIC_MODELS, AIRPURIFIER_TABLE_MODELS, DOMAIN
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotSwitchedEntity, exception_handler


@dataclass(frozen=True, kw_only=True)
class SwitchbotSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Switchbot switch entity."""

    is_on_fn: Callable[[switchbot.SwitchbotDevice], bool | None]
    turn_on_fn: Callable[[switchbot.SwitchbotDevice], Awaitable[Any]]
    turn_off_fn: Callable[[switchbot.SwitchbotDevice], Awaitable[Any]]


AIRPURIFIER_BASIC_SWITCHES: tuple[SwitchbotSwitchEntityDescription, ...] = (
    SwitchbotSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda device: device.is_child_lock_on(),
        turn_on_fn=lambda device: device.open_child_lock(),
        turn_off_fn=lambda device: device.close_child_lock(),
    ),
)

AIRPURIFIER_TABLE_SWITCHES: tuple[SwitchbotSwitchEntityDescription, ...] = (
    *AIRPURIFIER_BASIC_SWITCHES,
    SwitchbotSwitchEntityDescription(
        key="wireless_charging",
        translation_key="wireless_charging",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda device: device.is_wireless_charging_on(),
        turn_on_fn=lambda device: device.open_wireless_charging(),
        turn_off_fn=lambda device: device.close_wireless_charging(),
    ),
)

CIRCULATOR_FAN_PRO_SWITCHES: tuple[SwitchbotSwitchEntityDescription, ...] = (
    SwitchbotSwitchEntityDescription(
        key="vertical_oscillation",
        translation_key="vertical_oscillation",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda device: device.get_vertical_oscillating_state(),
        turn_on_fn=lambda device: device.set_vertical_oscillation(True),
        turn_off_fn=lambda device: device.set_vertical_oscillation(False),
    ),
)

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator = entry.runtime_data

    if isinstance(coordinator.device, switchbot.SwitchbotRelaySwitch2PM):
        entries = [
            SwitchbotMultiChannelSwitch(coordinator, channel)
            for channel in range(1, coordinator.device.channel + 1)
        ]
        async_add_entities(entries)
    elif coordinator.model in AIRPURIFIER_BASIC_MODELS:
        async_add_entities(
            [
                SwitchbotGenericSwitch(coordinator, desc)
                for desc in AIRPURIFIER_BASIC_SWITCHES
            ]
        )
    elif coordinator.model in AIRPURIFIER_TABLE_MODELS:
        async_add_entities(
            [
                SwitchbotGenericSwitch(coordinator, desc)
                for desc in AIRPURIFIER_TABLE_SWITCHES
            ]
        )
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities(
            [
                SwitchbotFanHorizontalOscillationSwitch(coordinator),
                SwitchbotFanVerticalOscillationSwitch(coordinator),
            ]
        )
    elif isinstance(coordinator.device, switchbot.SwitchbotCirculatorFanPro):
        async_add_entities(
            SwitchbotGenericSwitch(coordinator, desc)
            for desc in CIRCULATOR_FAN_PRO_SWITCHES
        )
    else:
        async_add_entities([SwitchBotSwitch(coordinator)])


class SwitchbotGenericSwitch(SwitchbotSwitchedEntity, SwitchEntity):
    """Representation of a Switchbot switch controlled via entity description."""

    entity_description: SwitchbotSwitchEntityDescription
    _device: switchbot.SwitchbotDevice

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        description: SwitchbotSwitchEntityDescription,
    ) -> None:
        """Initialize the Switchbot generic switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.base_unique_id}-{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self._device)

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        _LOGGER.debug(
            "Turning on %s for %s", self.entity_description.key, self._address
        )
        await self.entity_description.turn_on_fn(self._device)
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        _LOGGER.debug(
            "Turning off %s for %s", self.entity_description.key, self._address
        )
        await self.entity_description.turn_off_fn(self._device)
        self.async_write_ha_state()


class SwitchBotSwitch(SwitchbotSwitchedEntity, SwitchEntity, RestoreEntity):
    """Representation of a Switchbot switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "bot"
    _attr_name = None
    _device: switchbot.Switchbot

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._attr_is_on = False

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
        self._last_run_success = last_state.attributes.get("last_run_success")

    @property
    @override
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        return not self._device.switch_mode()

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if not self._device.switch_mode():
            return self._attr_is_on
        return self._device.is_on()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            **super().extra_state_attributes,
            "switch_mode": self._device.switch_mode(),
        }


class SwitchbotMultiChannelSwitch(SwitchbotSwitchedEntity, SwitchEntity):
    """Representation of a Switchbot multi-channel switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _device: switchbot.Switchbot
    _attr_name = None

    def __init__(
        self, coordinator: SwitchbotDataUpdateCoordinator, channel: int
    ) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._channel = channel
        self._attr_unique_id = f"{coordinator.base_unique_id}-{channel}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.base_unique_id}-channel-{channel}")},
            manufacturer="SwitchBot",
            model_id="RelaySwitch2PM",
            name=f"{coordinator.device_name} Channel {channel}",
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._device.is_on(self._channel)

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.debug(
            "Turn Switchbot device on %s, channel %d", self._address, self._channel
        )
        await self._device.turn_on(self._channel)
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.debug(
            "Turn Switchbot device off %s, channel %d", self._address, self._channel
        )
        await self._device.turn_off(self._channel)
        self.async_write_ha_state()


class SwitchbotFanOscillationSwitch(SwitchbotSwitchedEntity, SwitchEntity, abc.ABC):
    """Base class for fan oscillation switch entities."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _device: switchbot.SwitchbotStandingFan

    @property
    @abc.abstractmethod
    @override
    def is_on(self) -> bool | None:
        """Return true if oscillation is active."""

    @abc.abstractmethod
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable oscillation."""

    @abc.abstractmethod
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable oscillation."""


class SwitchbotFanHorizontalOscillationSwitch(SwitchbotFanOscillationSwitch):
    """Switch entity for fan horizontal (left-right) oscillation."""

    _attr_translation_key = "horizontal_oscillation"

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the horizontal oscillation switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}-horizontal-oscillation"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if horizontal oscillation is active."""
        return self._device.get_horizontal_oscillating_state()

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable horizontal oscillation."""
        await self._device.set_horizontal_oscillation(True)
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable horizontal oscillation."""
        await self._device.set_horizontal_oscillation(False)
        self.async_write_ha_state()


class SwitchbotFanVerticalOscillationSwitch(SwitchbotFanOscillationSwitch):
    """Switch entity for fan vertical (up-down) oscillation."""

    _attr_translation_key = "vertical_oscillation"

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the vertical oscillation switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}-vertical-oscillation"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if vertical oscillation is active."""
        return self._device.get_vertical_oscillating_state()

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable vertical oscillation."""
        await self._device.set_vertical_oscillation(True)
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable vertical oscillation."""
        await self._device.set_vertical_oscillation(False)
        self.async_write_ha_state()

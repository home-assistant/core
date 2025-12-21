"""Switcher integration Button platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from aioswitcher.api.remotes import SwitcherBreezeRemote
from aioswitcher.device import DeviceCategory, DeviceState, ThermostatSwing

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitcherConfigEntry
from .const import API_CONTROL_BREEZE_DEVICE, SIGNAL_DEVICE_ADD
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity
from .utils import get_breeze_remote_manager

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SwitcherThermostatButtonEntityDescription(ButtonEntityDescription):
    """Class to describe a Switcher Thermostat Button entity."""

    press_args: dict[str, Any]
    supported: Callable[[SwitcherBreezeRemote], bool]


THERMOSTAT_BUTTONS = [
    SwitcherThermostatButtonEntityDescription(
        key="assume_on",
        translation_key="assume_on",
        entity_category=EntityCategory.CONFIG,
        press_args={"state": DeviceState.ON, "update_state": True},
        supported=lambda _: True,
    ),
    SwitcherThermostatButtonEntityDescription(
        key="assume_off",
        translation_key="assume_off",
        entity_category=EntityCategory.CONFIG,
        press_args={"state": DeviceState.OFF, "update_state": True},
        supported=lambda _: True,
    ),
    SwitcherThermostatButtonEntityDescription(
        key="vertical_swing_on",
        translation_key="vertical_swing_on",
        press_args={"swing": ThermostatSwing.ON},
        supported=lambda remote: bool(remote.separated_swing_command),
    ),
    SwitcherThermostatButtonEntityDescription(
        key="vertical_swing_off",
        translation_key="vertical_swing_off",
        press_args={"swing": ThermostatSwing.OFF},
        supported=lambda remote: bool(remote.separated_swing_command),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitcherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switcher button from config entry."""

    async def async_add_buttons(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Get remote and add button from Switcher device."""
        data = cast(SwitcherBreezeRemote, coordinator.data)
        if coordinator.data.device_type.category == DeviceCategory.THERMOSTAT:
            remote: SwitcherBreezeRemote = await hass.async_add_executor_job(
                get_breeze_remote_manager(hass).get_remote, data.remote_id
            )
            async_add_entities(
                SwitcherThermostatButtonEntity(coordinator, description, remote)
                for description in THERMOSTAT_BUTTONS
                if description.supported(remote)
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_buttons)
    )


class SwitcherThermostatButtonEntity(SwitcherEntity, ButtonEntity):
    """Representation of a Switcher climate entity."""

    entity_description: SwitcherThermostatButtonEntityDescription

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        description: SwitcherThermostatButtonEntityDescription,
        remote: SwitcherBreezeRemote,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._remote = remote

        self._attr_unique_id = f"{coordinator.mac_address}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self._async_call_api(
            API_CONTROL_BREEZE_DEVICE,
            self._remote,
            **self.entity_description.press_args,
        )

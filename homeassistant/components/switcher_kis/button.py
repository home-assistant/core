"""Switcher integration Button platform."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from aioswitcher.api import (
    DeviceState,
    SwitcherApi,
    SwitcherBaseResponse,
    SwitcherType2Api,
    ThermostatSwing,
)
from aioswitcher.api.remotes import SwitcherBreezeRemote
from aioswitcher.device import DeviceCategory

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitcherConfigEntry
from .const import SIGNAL_DEVICE_ADD
from .coordinator import SwitcherDataUpdateCoordinator
from .utils import get_breeze_remote_manager


@dataclass(frozen=True, kw_only=True)
class SwitcherThermostatButtonEntityDescription(ButtonEntityDescription):
    """Class to describe a Switcher Thermostat Button entity."""

    press_fn: Callable[
        [SwitcherApi, SwitcherBreezeRemote],
        Coroutine[Any, Any, SwitcherBaseResponse],
    ]
    supported: Callable[[SwitcherBreezeRemote], bool]


THERMOSTAT_BUTTONS = [
    SwitcherThermostatButtonEntityDescription(
        key="assume_on",
        translation_key="assume_on",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api, remote: api.control_breeze_device(
            remote, state=DeviceState.ON, update_state=True
        ),
        supported=lambda _: True,
    ),
    SwitcherThermostatButtonEntityDescription(
        key="assume_off",
        translation_key="assume_off",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api, remote: api.control_breeze_device(
            remote, state=DeviceState.OFF, update_state=True
        ),
        supported=lambda _: True,
    ),
    SwitcherThermostatButtonEntityDescription(
        key="vertical_swing_on",
        translation_key="vertical_swing_on",
        press_fn=lambda api, remote: api.control_breeze_device(
            remote, swing=ThermostatSwing.ON
        ),
        supported=lambda remote: bool(remote.separated_swing_command),
    ),
    SwitcherThermostatButtonEntityDescription(
        key="vertical_swing_off",
        translation_key="vertical_swing_off",
        press_fn=lambda api, remote: api.control_breeze_device(
            remote, swing=ThermostatSwing.OFF
        ),
        supported=lambda remote: bool(remote.separated_swing_command),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitcherConfigEntry,
    async_add_entities: AddEntitiesCallback,
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


class SwitcherThermostatButtonEntity(
    CoordinatorEntity[SwitcherDataUpdateCoordinator], ButtonEntity
):
    """Representation of a Switcher climate entity."""

    entity_description: SwitcherThermostatButtonEntityDescription
    _attr_has_entity_name = True

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
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )

    async def async_press(self) -> None:
        """Press the button."""
        response: SwitcherBaseResponse | None = None
        error = None

        try:
            async with SwitcherType2Api(
                self.coordinator.data.ip_address,
                self.coordinator.data.device_id,
                self.coordinator.data.device_key,
            ) as swapi:
                response = await self.entity_description.press_fn(swapi, self._remote)
        except (TimeoutError, OSError, RuntimeError) as err:
            error = repr(err)

        if error or not response or not response.successful:
            self.coordinator.last_update_success = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Call api for {self.name} failed, response/error: {response or error}"
            )

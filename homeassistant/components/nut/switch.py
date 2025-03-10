"""Provides a switch for switchable NUT outlets."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import NutConfigEntry, PyNUTData
from .const import DOMAIN
from .sensor import _get_nut_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NUT switches."""
    available_switch_types: dict[str, SwitchEntityDescription] = {}

    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    data = pynut_data.data
    unique_id = pynut_data.unique_id
    status = coordinator.data

    # Dynamically add outlet switch types
    if (num_outlets := status.get("outlet.count")) is not None:
        for outlet_num in range(1, int(num_outlets) + 1):
            outlet_num_str = str(outlet_num)
            outlet_name: str = (
                status.get(f"outlet.{outlet_num_str}.name") or outlet_num_str
            )

            # Add as available only if switchable and with integration commands
            if (
                (status.get(f"outlet.{outlet_num_str}.switchable") == "yes")
                and (
                    f"outlet.{outlet_num_str}.load.on"
                    in pynut_data.user_available_commands
                )
                and (
                    f"outlet.{outlet_num_str}.load.off"
                    in pynut_data.user_available_commands
                )
            ):
                available_switch_types |= {
                    f"outlet.{outlet_num_str}.load.poweronoff": SwitchEntityDescription(
                        key=f"outlet.{outlet_num_str}.load.poweronoff",
                        translation_key="outlet_number_load_poweronoff",
                        translation_placeholders={"outlet_name": outlet_name},
                        device_class=SwitchDeviceClass.OUTLET,
                        entity_registry_enabled_default=True,
                    ),
                }

        async_add_entities(
            NUTSwitch(
                coordinator,
                available_switch_types[switch_type],
                data,
                unique_id,
            )
            for switch_type in available_switch_types
        )


class NUTSwitch(CoordinatorEntity[DataUpdateCoordinator[dict[str, str]]], SwitchEntity):
    """Representation of a switch entity for NUT status values."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, str]],
        switch_description: SwitchEntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.pynut_data = data
        self.entity_description = switch_description

        device_name = data.name.title()
        self._attr_unique_id = f"{unique_id}_{switch_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_device_info.update(_get_nut_device_info(data))

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        status = self.coordinator.data

        name_list = self.entity_description.key.split(".")
        return status.get(f"{name_list[0]}.{name_list[1]}.status") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        _LOGGER.debug("turn_on -> kwargs: %s", kwargs)

        name_list = self.entity_description.key.split(".")
        command_name = f"{name_list[0]}.{name_list[1]}.load.on"
        await self.pynut_data.async_run_command(command_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        _LOGGER.debug("turn_off -> kwargs: %s", kwargs)

        name_list = self.entity_description.key.split(".")
        command_name = f"{name_list[0]}.{name_list[1]}.load.off"
        await self.pynut_data.async_run_command(command_name)

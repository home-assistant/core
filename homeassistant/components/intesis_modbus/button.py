"""Buttons for the commands of an Intesis gateway and its air conditioner."""

from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Final, override

from intesis_gw_modbus import IntesisSingleUnitGateway
from modbus_connection import ModbusTimeoutError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntesisConfigEntry, IntesisCoordinator, IntesisUnitCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class IntesisButtonEntityDescription(ButtonEntityDescription):
    """A command, and the gateway sub-system it depends on."""

    report_name: str
    press_fn: Callable[[IntesisSingleUnitGateway], Awaitable[None]]


async def _async_reset_gateway(device: IntesisSingleUnitGateway) -> None:
    """Reset the gateway, which restarts without answering the request."""
    with suppress(ModbusTimeoutError):
        await device.async_reset_gateway()


GATEWAY_BUTTONS: Final[tuple[IntesisButtonEntityDescription, ...]] = (
    IntesisButtonEntityDescription(
        key="reset_gateway",
        translation_key="reset_gateway",
        report_name="control",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=_async_reset_gateway,
    ),
)

UNIT_BUTTONS: Final[tuple[IntesisButtonEntityDescription, ...]] = (
    IntesisButtonEntityDescription(
        key="clear_external_temperature",
        translation_key="clear_external_temperature",
        report_name="limits",
        entity_category=EntityCategory.CONFIG,
        # Without an external reference the unit regulates on its own sensor
        press_fn=lambda device: device.async_set_external_temperature(None),
    ),
    IntesisButtonEntityDescription(
        key="reset_error",
        translation_key="reset_error",
        report_name="control",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda device: device.async_reset_error(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of the gateway and its air conditioner."""
    data = entry.runtime_data
    async_add_entities(
        [
            *(
                IntesisButton(data.gateway, description)
                for description in GATEWAY_BUTTONS
            ),
            *(IntesisButton(data.unit, description) for description in UNIT_BUTTONS),
        ]
    )


class IntesisButton(IntesisEntity, ButtonEntity):
    """A command for an Intesis gateway or the air conditioner behind it."""

    entity_description: IntesisButtonEntityDescription

    def __init__(
        self,
        coordinator: IntesisCoordinator | IntesisUnitCoordinator,
        description: IntesisButtonEntityDescription,
    ) -> None:
        """Bind to the command the description sends."""
        super().__init__(coordinator, description.key, description.report_name)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Send the command to the gateway."""
        await self._async_write(
            lambda: self.entity_description.press_fn(self.coordinator.device)
        )

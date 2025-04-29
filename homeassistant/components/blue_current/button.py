"""Support for Blue Current buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from bluecurrent_api.client import Client

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BlueCurrentConfigEntry, Connector
from .entity import ChargepointEntity


@dataclass(kw_only=True, frozen=True)
class ChargePointButtonEntityDescription(ButtonEntityDescription):
    """Describes a Blue Current button entity."""

    function: Callable[[Client, str], Coroutine[Any, Any, None]]


CHARGE_POINT_BUTTONS = (
    ChargePointButtonEntityDescription(
        key="reset",
        translation_key="reset",
        function=lambda client, evse_id: client.reset(evse_id),
        device_class=ButtonDeviceClass.RESTART,
    ),
    ChargePointButtonEntityDescription(
        key="reboot",
        translation_key="reboot",
        function=lambda client, evse_id: client.reboot(evse_id),
        device_class=ButtonDeviceClass.RESTART,
    ),
    ChargePointButtonEntityDescription(
        key="stop_charge_session",
        translation_key="stop_charge_session",
        function=lambda client, evse_id: client.stop_session(evse_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueCurrentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Blue Current buttons."""
    connector: Connector = entry.runtime_data
    async_add_entities(
        ChargePointButton(
            connector,
            button,
            evse_id,
        )
        for evse_id in connector.charge_points
        for button in CHARGE_POINT_BUTTONS
    )


class ChargePointButton(ChargepointEntity, ButtonEntity):
    """Define a charge point button."""

    def __init__(
        self,
        connector: Connector,
        description: ChargePointButtonEntityDescription,
        evse_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(connector, evse_id)

        self.has_value = True
        self.entity_description: ChargePointButtonEntityDescription = description
        self._attr_unique_id = f"{description.key}_{evse_id}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.function(self.connector.client, self.evse_id)

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""

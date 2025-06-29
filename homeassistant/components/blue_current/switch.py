"""Support for Blue Current switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bluecurrent_api import Client

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PLUG_AND_CHARGE, BlueCurrentConfigEntry, Connector
from .const import (
    AVAILABLE,
    BLOCK,
    LINKED_CHARGE_CARDS,
    PUBLIC_CHARGING,
    UNAVAILABLE,
    VALUE,
)
from .entity import ChargepointEntity


@dataclass(kw_only=True, frozen=True)
class BlueCurrentSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Blue Current switch entity."""

    function: Callable[[Client, str, bool], Any]

    update_lastest_data: Callable[[str, Connector], tuple[bool, bool]]
    """Update the switch based on the latest data received from the websocket. The first returned boolean is _attr_is_on, the second one has_value."""

    on_switch_update: Callable[[str, Connector, bool], None] | None = None
    """
    Change the settings on the charge point object when the value of the switch has changed.
    """


def update_on_value_and_activity(
    key: str, evse_id: str, connector: Connector, reverse_is_on: bool = False
) -> tuple[bool, bool]:
    """Return the updated state of the switch based on received chargepoint data and activity."""

    data_object = connector.charge_points[evse_id].get(key)
    is_on = data_object[VALUE] if data_object is not None else None
    activity = connector.charge_points[evse_id].get("activity")

    if is_on is not None and activity == AVAILABLE:
        return is_on if not reverse_is_on else not is_on, True
    return False, False


def update_block_switch(evse_id: str, connector: Connector) -> tuple[bool, bool]:
    """Return the updated data for a block switch."""
    activity = connector.charge_points[evse_id].get("activity")
    return activity == UNAVAILABLE, activity in [AVAILABLE, UNAVAILABLE]


def update_charge_point(
    key: str, evse_id: str, connector: Connector, new_switch_value: bool
) -> None:
    """Change charge point data when the state of the switch changes."""
    data_objects = connector.charge_points[evse_id].get(key)
    if data_objects is not None:
        data_objects[VALUE] = new_switch_value


SWITCHES = (
    BlueCurrentSwitchEntityDescription(
        key=PLUG_AND_CHARGE,
        translation_key=PLUG_AND_CHARGE,
        function=lambda client, evse_id, value: client.set_plug_and_charge(
            evse_id, value
        ),
        update_lastest_data=lambda evse_id, connector: update_on_value_and_activity(
            PLUG_AND_CHARGE, evse_id, connector
        ),
        on_switch_update=lambda evse_id,
        connector,
        new_switch_value: update_charge_point(
            PLUG_AND_CHARGE, evse_id, connector, new_switch_value
        ),
    ),
    BlueCurrentSwitchEntityDescription(
        key=LINKED_CHARGE_CARDS,
        translation_key=LINKED_CHARGE_CARDS,
        function=lambda client, evse_id, value: client.set_linked_charge_cards_only(
            evse_id, value
        ),
        update_lastest_data=lambda evse_id, connector: update_on_value_and_activity(
            PUBLIC_CHARGING, evse_id, connector, reverse_is_on=True
        ),
        on_switch_update=lambda evse_id,
        connector,
        new_switch_value: update_charge_point(
            PUBLIC_CHARGING, evse_id, connector, not new_switch_value
        ),
    ),
    BlueCurrentSwitchEntityDescription(
        key=BLOCK,
        translation_key=BLOCK,
        function=lambda client, evse_id, value: client.block(evse_id, value),
        update_lastest_data=update_block_switch,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueCurrentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Blue Current switches."""
    connector = entry.runtime_data

    async_add_entities(
        ChargePointSwitch(
            connector,
            evse_id,
            switch,
        )
        for evse_id in connector.charge_points
        for switch in SWITCHES
    )


class ChargePointSwitch(ChargepointEntity, SwitchEntity):
    """Base charge point switch."""

    has_value = True
    entity_description: BlueCurrentSwitchEntityDescription

    def __init__(
        self,
        connector: Connector,
        evse_id: str,
        switch: BlueCurrentSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(connector, evse_id)

        self.key = switch.key
        self.entity_description = switch
        self.evse_id = evse_id
        self._attr_available = True
        self._attr_unique_id = f"{switch.key}_{evse_id}"

    async def call_function(self, value: bool) -> None:
        """Call the function to set setting."""
        await self.entity_description.function(
            self.connector.client, self.evse_id, value
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_function(True)
        self._attr_is_on = True
        if self.entity_description.on_switch_update is not None:
            self.entity_description.on_switch_update(self.evse_id, self.connector, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_function(False)
        self._attr_is_on = False
        if self.entity_description.on_switch_update is not None:
            self.entity_description.on_switch_update(
                self.evse_id, self.connector, False
            )
        self.async_write_ha_state()

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the switch."""
        new_state = self.entity_description.update_lastest_data(
            self.evse_id, self.connector
        )
        self._attr_is_on = new_state[0]
        self.has_value = new_state[1]

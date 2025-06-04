"""Support for Blue Current switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bluecurrent_api import Client

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
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


SWITCHES = (
    BlueCurrentSwitchEntityDescription(
        key=PLUG_AND_CHARGE,
        device_class=SwitchDeviceClass.SWITCH,
        translation_key=PLUG_AND_CHARGE,
        icon="mdi:ev-plug-type2",
        function=lambda client, evse_id, value: client.set_plug_and_charge(
            evse_id, value
        ),
        has_entity_name=True,
    ),
    BlueCurrentSwitchEntityDescription(
        key=LINKED_CHARGE_CARDS,
        device_class=SwitchDeviceClass.SWITCH,
        translation_key=LINKED_CHARGE_CARDS,
        icon="mdi:account-group",
        function=lambda client, evse_id, value: client.set_linked_charge_cards_only(
            evse_id, value
        ),
        has_entity_name=True,
    ),
    BlueCurrentSwitchEntityDescription(
        key=BLOCK,
        device_class=SwitchDeviceClass.SWITCH,
        translation_key=BLOCK,
        icon="mdi:lock",
        function=lambda client, evse_id, value: client.block(evse_id, value),
        has_entity_name=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlueCurrentConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Blue Current switches."""
    connector: Connector = entry.runtime_data

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

    _attr_should_poll = False
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
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_function(False)
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def update_from_latest_data(self) -> None:
        """Fetch new state data for the switch."""

        def get_updated_switch_state(key: str = self.key) -> bool | None:
            data_object = self.connector.charge_points[self.evse_id].get(key)
            return data_object[VALUE] if data_object is not None else None

        activity = self.connector.charge_points[self.evse_id].get("activity")

        if self.key == PLUG_AND_CHARGE:
            is_on = get_updated_switch_state()

            if is_on is not None and activity == AVAILABLE:
                self._attr_is_on = is_on
                self.has_value = True
            else:
                self.has_value = False

        elif self.key == LINKED_CHARGE_CARDS:
            is_on = get_updated_switch_state(PUBLIC_CHARGING)

            if is_on is not None and activity == AVAILABLE:
                self._attr_is_on = not is_on
                self.has_value = True
            else:
                self.has_value = False

        elif self.key == BLOCK:
            self._attr_is_on = activity == UNAVAILABLE
            self.has_value = activity in [AVAILABLE, UNAVAILABLE]

"""Support for LCN covers."""

from collections.abc import Iterable
from functools import partial
from typing import Any

import pypck

from homeassistant.components.cover import DOMAIN as DOMAIN_COVER, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    CONF_MOTOR,
    CONF_REVERSE_TIME,
    DOMAIN,
)
from .entity import LcnEntity
from .helpers import InputType

PARALLEL_UPDATES = 0


def add_lcn_entities(
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities: list[LcnOutputsCover | LcnRelayCover] = []
    for entity_config in entity_configs:
        if entity_config[CONF_DOMAIN_DATA][CONF_MOTOR] in "OUTPUTS":
            entities.append(LcnOutputsCover(entity_config, config_entry))
        else:  # in RELAYS
            entities.append(LcnRelayCover(entity_config, config_entry))

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN cover entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    hass.data[DOMAIN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS].update(
        {DOMAIN_COVER: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_COVER
        ),
    )


class LcnOutputsCover(LcnEntity, CoverEntity):
    """Representation of a LCN cover connected to output ports."""

    _attr_is_closed = False
    _attr_is_closing = False
    _attr_is_opening = False
    _attr_assumed_state = True

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN cover."""
        super().__init__(config, config_entry)

        self.output_ids = [
            pypck.lcn_defs.OutputPort["OUTPUTUP"].value,
            pypck.lcn_defs.OutputPort["OUTPUTDOWN"].value,
        ]
        if CONF_REVERSE_TIME in config[CONF_DOMAIN_DATA]:
            self.reverse_time = pypck.lcn_defs.MotorReverseTime[
                config[CONF_DOMAIN_DATA][CONF_REVERSE_TIME]
            ]
        else:
            self.reverse_time = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTUP"]
            )
            await self.device_connection.activate_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTDOWN"]
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTUP"]
            )
            await self.device_connection.cancel_status_request_handler(
                pypck.lcn_defs.OutputPort["OUTPUTDOWN"]
            )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        state = pypck.lcn_defs.MotorStateModifier.DOWN
        if not await self.device_connection.control_motors_outputs(
            state, self.reverse_time
        ):
            return
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        state = pypck.lcn_defs.MotorStateModifier.UP
        if not await self.device_connection.control_motors_outputs(
            state, self.reverse_time
        ):
            return
        self._attr_is_closed = False
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        state = pypck.lcn_defs.MotorStateModifier.STOP
        if not await self.device_connection.control_motors_outputs(state):
            return
        self._attr_is_closing = False
        self._attr_is_opening = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set cover states when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() not in self.output_ids
        ):
            return

        if input_obj.get_percent() > 0:  # motor is on
            if input_obj.get_output_id() == self.output_ids[0]:
                self._attr_is_opening = True
                self._attr_is_closing = False
            else:  # self.output_ids[1]
                self._attr_is_opening = False
                self._attr_is_closing = True
            self._attr_is_closed = self._attr_is_closing
        else:  # motor is off
            # cover is assumed to be closed if we were in closing state before
            self._attr_is_closed = self._attr_is_closing
            self._attr_is_closing = False
            self._attr_is_opening = False

        self.async_write_ha_state()


class LcnRelayCover(LcnEntity, CoverEntity):
    """Representation of a LCN cover connected to relays."""

    _attr_is_closed = False
    _attr_is_closing = False
    _attr_is_opening = False
    _attr_assumed_state = True

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN cover."""
        super().__init__(config, config_entry)

        self.motor = pypck.lcn_defs.MotorPort[config[CONF_DOMAIN_DATA][CONF_MOTOR]]
        self.motor_port_onoff = self.motor.value * 2
        self.motor_port_updown = self.motor_port_onoff + 1

        self._is_closed = False
        self._is_closing = False
        self._is_opening = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.motor)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.motor)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.DOWN
        if not await self.device_connection.control_motors_relays(states):
            return
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.UP
        if not await self.device_connection.control_motors_relays(states):
            return
        self._attr_is_closed = False
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        states = [pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = pypck.lcn_defs.MotorStateModifier.STOP
        if not await self.device_connection.control_motors_relays(states):
            return
        self._attr_is_closing = False
        self._attr_is_opening = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set cover states when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        states = input_obj.states  # list of boolean values (relay on/off)
        if states[self.motor_port_onoff]:  # motor is on
            self._attr_is_opening = not states[self.motor_port_updown]  # set direction
            self._attr_is_closing = states[self.motor_port_updown]  # set direction
        else:  # motor is off
            self._attr_is_opening = False
            self._attr_is_closing = False
            self._attr_is_closed = states[self.motor_port_updown]

        self.async_write_ha_state()

"""Support for LCN covers."""

from collections.abc import Iterable
from functools import partial
from typing import Any

import pypck

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as DOMAIN_COVER,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    CONF_MOTOR,
    CONF_POSITIONING_MODE,
    CONF_REVERSE_TIME,
    DOMAIN,
)
from .entity import LcnEntity
from .helpers import InputType

PARALLEL_UPDATES = 0


def add_lcn_entities(
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        if not await self.device_connection.control_motor_outputs(
            state, self.reverse_time
        ):
            return
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        state = pypck.lcn_defs.MotorStateModifier.UP
        if not await self.device_connection.control_motor_outputs(
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
        if not await self.device_connection.control_motor_outputs(state):
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
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    positioning_mode: pypck.lcn_defs.MotorPositioningMode

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN cover."""
        super().__init__(config, config_entry)

        self.positioning_mode = pypck.lcn_defs.MotorPositioningMode(
            config[CONF_DOMAIN_DATA].get(
                CONF_POSITIONING_MODE, pypck.lcn_defs.MotorPositioningMode.NONE.value
            )
        )

        if self.positioning_mode != pypck.lcn_defs.MotorPositioningMode.NONE:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

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
            await self.device_connection.activate_status_request_handler(
                self.motor, self.positioning_mode
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.motor)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if not await self.device_connection.control_motor_relays(
            self.motor.value,
            pypck.lcn_defs.MotorStateModifier.DOWN,
            self.positioning_mode,
        ):
            return
        self._attr_is_opening = False
        self._attr_is_closing = True
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if not await self.device_connection.control_motor_relays(
            self.motor.value,
            pypck.lcn_defs.MotorStateModifier.UP,
            self.positioning_mode,
        ):
            return
        self._attr_is_closed = False
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if not await self.device_connection.control_motor_relays(
            self.motor.value,
            pypck.lcn_defs.MotorStateModifier.STOP,
            self.positioning_mode,
        ):
            return
        self._attr_is_closing = False
        self._attr_is_opening = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if not await self.device_connection.control_motor_relays_position(
            self.motor.value, position, mode=self.positioning_mode
        ):
            return
        self._attr_is_closed = (self._attr_current_cover_position == 0) & (
            position == 0
        )
        if self._attr_current_cover_position is not None:
            self._attr_is_closing = self._attr_current_cover_position > position
            self._attr_is_opening = self._attr_current_cover_position < position
        self._attr_current_cover_position = position

        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set cover states when LCN input object (command) is received."""
        if isinstance(input_obj, pypck.inputs.ModStatusRelays):
            self._attr_is_opening = input_obj.is_opening(self.motor.value)
            self._attr_is_closing = input_obj.is_closing(self.motor.value)

            if self.positioning_mode == pypck.lcn_defs.MotorPositioningMode.NONE:
                self._attr_is_closed = input_obj.is_assumed_closed(self.motor.value)
            self.async_write_ha_state()
        elif (
            isinstance(
                input_obj,
                (
                    pypck.inputs.ModStatusMotorPositionBS4,
                    pypck.inputs.ModStatusMotorPositionModule,
                ),
            )
            and input_obj.motor == self.motor.value
        ):
            self._attr_current_cover_position = input_obj.position
            if self._attr_current_cover_position in [0, 100]:
                self._attr_is_opening = False
                self._attr_is_closing = False
            self._attr_is_closed = self._attr_current_cover_position == 0
            self.async_write_ha_state()

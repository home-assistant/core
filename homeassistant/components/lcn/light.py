"""Support for LCN lights."""

from collections.abc import Iterable
from functools import partial
from typing import Any

import pypck

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN as DOMAIN_LIGHT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DIMMABLE,
    CONF_DOMAIN_DATA,
    CONF_OUTPUT,
    CONF_TRANSITION,
    DOMAIN,
    OUTPUT_PORTS,
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
    entities: list[LcnOutputLight | LcnRelayLight] = []
    for entity_config in entity_configs:
        if entity_config[CONF_DOMAIN_DATA][CONF_OUTPUT] in OUTPUT_PORTS:
            entities.append(LcnOutputLight(entity_config, config_entry))
        else:  # in RELAY_PORTS
            entities.append(LcnRelayLight(entity_config, config_entry))

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN light entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    hass.data[DOMAIN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS].update(
        {DOMAIN_LIGHT: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_LIGHT
        ),
    )


class LcnOutputLight(LcnEntity, LightEntity):
    """Representation of a LCN light for output ports."""

    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_is_on = False
    _attr_brightness = 255

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN light."""
        super().__init__(config, config_entry)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

        self._transition = pypck.lcn_defs.time_to_ramp_value(
            config[CONF_DOMAIN_DATA][CONF_TRANSITION]
        )
        self.dimmable = config[CONF_DOMAIN_DATA][CONF_DIMMABLE]

        self._is_dimming_to_zero = False

        if self.dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.output)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.output)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if ATTR_BRIGHTNESS in kwargs:
            percent = int(kwargs[ATTR_BRIGHTNESS] / 255.0 * 100)
        else:
            percent = 100
        if ATTR_TRANSITION in kwargs:
            transition = pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000
            )
        else:
            transition = self._transition

        if not await self.device_connection.dim_output(
            self.output.value, percent, transition
        ):
            return
        self._attr_is_on = True
        self._is_dimming_to_zero = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if ATTR_TRANSITION in kwargs:
            transition = pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000
            )
        else:
            transition = self._transition

        if not await self.device_connection.dim_output(
            self.output.value, 0, transition
        ):
            return
        self._is_dimming_to_zero = bool(transition)
        self._attr_is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set light state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() != self.output.value
        ):
            return

        self._attr_brightness = int(input_obj.get_percent() / 100.0 * 255)
        if self._attr_brightness == 0:
            self._is_dimming_to_zero = False
        if not self._is_dimming_to_zero and self._attr_brightness is not None:
            self._attr_is_on = self._attr_brightness > 0
        self.async_write_ha_state()


class LcnRelayLight(LcnEntity, LightEntity):
    """Representation of a LCN light for relay ports."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN light."""
        super().__init__(config, config_entry)

        self.output = pypck.lcn_defs.RelayPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.output)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.output)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.ON
        if not await self.device_connection.control_relays(states):
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        states = [pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = pypck.lcn_defs.RelayStateModifier.OFF
        if not await self.device_connection.control_relays(states):
            return
        self._attr_is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set light state when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        self._attr_is_on = input_obj.get_state(self.output.value)
        self.async_write_ha_state()

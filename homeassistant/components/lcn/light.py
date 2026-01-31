"""Support for LCN lights."""

from collections.abc import Iterable
from datetime import timedelta
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
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import (
    CONF_DIMMABLE,
    CONF_DOMAIN_DATA,
    CONF_OUTPUT,
    CONF_TRANSITION,
    OUTPUT_PORTS,
)
from .entity import LcnEntity
from .helpers import InputType, LcnConfigEntry

BRIGHTNESS_SCALE = (1, 100)

PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(minutes=10)


def add_lcn_entities(
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LCN light entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    config_entry.runtime_data.add_entities_callbacks.update(
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

    def __init__(self, config: ConfigType, config_entry: LcnConfigEntry) -> None:
        """Initialize the LCN light."""
        super().__init__(config, config_entry)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

        self._transition = pypck.lcn_defs.time_to_ramp_value(
            config[CONF_DOMAIN_DATA][CONF_TRANSITION] * 1000.0
        )
        self.dimmable = config[CONF_DOMAIN_DATA][CONF_DIMMABLE]

        if self.dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if ATTR_TRANSITION in kwargs:
            transition = pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000
            )
        else:
            transition = self._transition

        if ATTR_BRIGHTNESS in kwargs:
            percent = int(
                brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
            )
            if not await self.device_connection.dim_output(
                self.output.value, percent, transition
            ):
                return
        elif not self.is_on:
            if not await self.device_connection.toggle_output(
                self.output.value, transition, to_memory=True
            ):
                return
        else:
            return

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if ATTR_TRANSITION in kwargs:
            transition = pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000
            )
        else:
            transition = self._transition

        if self.is_on:
            if not await self.device_connection.toggle_output(
                self.output.value, transition, to_memory=True
            ):
                return
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the state of the entity."""
        self._attr_available = (
            await self.device_connection.request_status_output(
                self.output, SCAN_INTERVAL.seconds
            )
            is not None
        )

    def input_received(self, input_obj: InputType) -> None:
        """Set light state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() != self.output.value
        ):
            return
        self._attr_available = True
        percent = input_obj.get_percent()
        self._attr_brightness = value_to_brightness(BRIGHTNESS_SCALE, percent)
        self._attr_is_on = bool(percent)
        self.async_write_ha_state()


class LcnRelayLight(LcnEntity, LightEntity):
    """Representation of a LCN light for relay ports."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: LcnConfigEntry) -> None:
        """Initialize the LCN light."""
        super().__init__(config, config_entry)

        self.output = pypck.lcn_defs.RelayPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

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

    async def async_update(self) -> None:
        """Update the state of the entity."""
        self._attr_available = (
            await self.device_connection.request_status_relays(SCAN_INTERVAL.seconds)
            is not None
        )

    def input_received(self, input_obj: InputType) -> None:
        """Set light state when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return
        self._attr_available = True
        self._attr_is_on = input_obj.get_state(self.output.value)
        self.async_write_ha_state()

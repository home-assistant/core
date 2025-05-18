"""Support for LCN switches."""

from collections.abc import Iterable
from functools import partial
from typing import Any

import pypck

from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_DOMAIN_DATA,
    CONF_OUTPUT,
    DOMAIN,
    OUTPUT_PORTS,
    RELAY_PORTS,
    SETPOINTS,
)
from .entity import LcnEntity
from .helpers import InputType

PARALLEL_UPDATES = 0


def add_lcn_switch_entities(
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities: list[
        LcnOutputSwitch | LcnRelaySwitch | LcnRegulatorLockSwitch | LcnKeyLockSwitch
    ] = []
    for entity_config in entity_configs:
        if entity_config[CONF_DOMAIN_DATA][CONF_OUTPUT] in OUTPUT_PORTS:
            entities.append(LcnOutputSwitch(entity_config, config_entry))
        elif entity_config[CONF_DOMAIN_DATA][CONF_OUTPUT] in RELAY_PORTS:
            entities.append(LcnRelaySwitch(entity_config, config_entry))
        elif entity_config[CONF_DOMAIN_DATA][CONF_OUTPUT] in SETPOINTS:
            entities.append(LcnRegulatorLockSwitch(entity_config, config_entry))
        else:  # in KEYS
            entities.append(LcnKeyLockSwitch(entity_config, config_entry))

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    add_entities = partial(
        add_lcn_switch_entities,
        config_entry,
        async_add_entities,
    )

    hass.data[DOMAIN][config_entry.entry_id][ADD_ENTITIES_CALLBACKS].update(
        {DOMAIN_SWITCH: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_SWITCH
        ),
    )


class LcnOutputSwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for output ports."""

    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN switch."""
        super().__init__(config, config_entry)

        self.output = pypck.lcn_defs.OutputPort[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]

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
        if not await self.device_connection.dim_output(self.output.value, 100, 0):
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if not await self.device_connection.dim_output(self.output.value, 0, 0):
            return
        self._attr_is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set switch state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusOutput)
            or input_obj.get_output_id() != self.output.value
        ):
            return

        self._attr_is_on = input_obj.get_percent() > 0
        self.async_write_ha_state()


class LcnRelaySwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for relay ports."""

    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN switch."""
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
        """Set switch state when LCN input object (command) is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusRelays):
            return

        self._attr_is_on = input_obj.get_state(self.output.value)
        self.async_write_ha_state()


class LcnRegulatorLockSwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for regulator locks."""

    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN switch."""
        super().__init__(config, config_entry)

        self.setpoint_variable = pypck.lcn_defs.Var[
            config[CONF_DOMAIN_DATA][CONF_OUTPUT]
        ]
        self.reg_id = pypck.lcn_defs.Var.to_set_point_id(self.setpoint_variable)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(
                self.setpoint_variable
            )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(
                self.setpoint_variable
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if not await self.device_connection.lock_regulator(self.reg_id, True):
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if not await self.device_connection.lock_regulator(self.reg_id, False):
            return
        self._attr_is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set switch state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusVar)
            or input_obj.get_var() != self.setpoint_variable
        ):
            return

        self._attr_is_on = input_obj.get_value().is_locked_regulator()
        self.async_write_ha_state()


class LcnKeyLockSwitch(LcnEntity, SwitchEntity):
    """Representation of a LCN switch for key locks."""

    _attr_is_on = False

    def __init__(self, config: ConfigType, config_entry: ConfigEntry) -> None:
        """Initialize the LCN switch."""
        super().__init__(config, config_entry)

        self.key = pypck.lcn_defs.Key[config[CONF_DOMAIN_DATA][CONF_OUTPUT]]
        self.table_id = ord(self.key.name[0]) - 65
        self.key_id = int(self.key.name[1]) - 1

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.key)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        states = [pypck.lcn_defs.KeyLockStateModifier.NOCHANGE] * 8
        states[self.key_id] = pypck.lcn_defs.KeyLockStateModifier.ON

        if not await self.device_connection.lock_keys(self.table_id, states):
            return

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        states = [pypck.lcn_defs.KeyLockStateModifier.NOCHANGE] * 8
        states[self.key_id] = pypck.lcn_defs.KeyLockStateModifier.OFF

        if not await self.device_connection.lock_keys(self.table_id, states):
            return

        self._attr_is_on = False
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set switch state when LCN input object (command) is received."""
        if (
            not isinstance(input_obj, pypck.inputs.ModStatusKeyLocks)
            or self.key not in pypck.lcn_defs.Key
        ):
            return

        self._attr_is_on = input_obj.get_state(self.table_id, self.key_id)
        self.async_write_ha_state()

"""Representation of Z-Wave switches."""

from __future__ import annotations

from typing import Any

from zwave_js_server.const import TARGET_VALUE_PROPERTY
from zwave_js_server.const.command_class.barrier_operator import (
    BarrierEventSignalingSubsystemState,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.util.multicast import async_multicast_set_value

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, EntityCategory
from homeassistant.core import (
    EntityServiceResponse,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .helpers import ValueDataType
from .models import ZwaveJSConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZwaveJSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client = config_entry.runtime_data.client

    @callback
    def async_add_switch(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Switch."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "barrier_event_signaling_state":
            entities.append(
                ZWaveBarrierEventSignalingSwitch(config_entry, driver, info)
            )
        elif info.platform_hint == "config_parameter":
            entities.append(ZWaveConfigParameterSwitch(config_entry, driver, info))
        elif info.platform_hint == "indicator":
            entities.append(ZWaveIndicatorSwitch(config_entry, driver, info))
        else:
            entities.append(ZWaveSwitch(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SWITCH_DOMAIN}",
            async_add_switch,
        )
    )

    # --- register the batched handler ---
    entity_component: EntityComponent = hass.data[SWITCH_DOMAIN]
    entity_component.async_register_batched_handler(
        name=SERVICE_TURN_ON,
        config_entry=config_entry,
        handler=async_batched_zwave_js_on_off,
    )
    entity_component.async_register_batched_handler(
        name=SERVICE_TURN_OFF,
        config_entry=config_entry,
        handler=async_batched_zwave_js_on_off,
    )


VALUE_ID_SWITCH_BINARY: str = "targetValue"


async def async_batched_zwave_js_on_off(
    config_entry: ConfigEntry,
    entities: list[Entity],
    call: ServiceCall,
) -> EntityServiceResponse | None:
    """Batched handler for turn_on and turn_off using virtual multicast."""
    if not entities:
        return None

    if call.service == SERVICE_TURN_ON:
        value: bool = True
    elif call.service == SERVICE_TURN_OFF:
        value = False
    else:
        raise HomeAssistantError(f"Unsupported service: {call.service}")

    config_param_entities = [
        e for e in entities if isinstance(e, ZWaveConfigParameterSwitch)
    ]

    binary_switch_entities = [
        e
        for e in entities
        if isinstance(e, ZWaveSwitch) and not isinstance(e, ZWaveConfigParameterSwitch)
    ]
    unsupported_entities = [
        e
        for e in entities
        if not isinstance(e, (ZWaveSwitch, ZWaveConfigParameterSwitch))
    ]

    if unsupported_entities:
        LOGGER.warning(
            "Batched Z-Wave handler received unsupported entities: %s",
            unsupported_entities,
        )

    client = None
    # For regular binary switches
    if binary_switch_entities:
        first_binary_switch_entity = binary_switch_entities[0]
        binary_switch_zwave_value = first_binary_switch_entity.get_zwave_value(
            TARGET_VALUE_PROPERTY
        )
        if binary_switch_zwave_value is None:
            raise HomeAssistantError(
                f"Unable to resolve Z-Wave value for entity {first_binary_switch_entity}, node {first_binary_switch_entity.info.node}"
            )

        binary_switch_value_data: ValueDataType = {
            "commandClass": binary_switch_zwave_value.command_class,
            "property": binary_switch_zwave_value.property_,
        }
        if binary_switch_zwave_value.endpoint is not None:
            binary_switch_value_data["endpoint"] = binary_switch_zwave_value.endpoint
        client = binary_switch_entities[0].driver.client

    # For config parameter switches
    if config_param_entities:
        config_entity = config_param_entities[0]

        config_zwave_value = config_entity.get_zwave_value(
            value_property=VALUE_ID_SWITCH_BINARY
        )
        if config_zwave_value is None:
            raise HomeAssistantError(
                f"Unable to resolve Z-Wave value for config entity {config_entity}, node {config_entity.info.node}"
            )

        config_value_data: ValueDataType = {
            "commandClass": config_zwave_value.command_class,
            "property": config_zwave_value.property_,
        }
        if config_zwave_value.endpoint is not None:
            config_value_data["endpoint"] = config_zwave_value.endpoint
        client = config_param_entities[0].driver.client

    if client is None:
        LOGGER.error("Zwave Switch Multicast had no entities")
        return None

    # We could probably gather these, but it doesn't seem like that would occur too often
    # --- multicast for normal switches ---
    if binary_switch_entities:
        LOGGER.debug(
            "Calling Zwave Multicast with value_data %s, value %s for entities %s",
            binary_switch_value_data,
            value,
            binary_switch_entities,
        )
        await async_multicast_set_value(
            client=client,
            new_value=value,
            value_data=binary_switch_value_data,
            nodes=[n.info.node for n in binary_switch_entities],
            options=None,
        )

    # --- multicast for config parameter switches ---
    if config_param_entities:
        LOGGER.debug(
            "Calling Zwave Config Parameter Multicast with value_data %s, value %s for entities %s",
            config_value_data,
            value,
            config_param_entities,
        )
        await async_multicast_set_value(
            client=client,
            new_value=value,
            value_data=config_value_data,
            nodes=[n.info.node for n in config_param_entities],
            options=None,
        )

    return None


class ZWaveSwitch(ZWaveBaseEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    def __init__(
        self, config_entry: ZwaveJSConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the switch."""
        super().__init__(config_entry, driver, info)

        self._target_value = self.get_zwave_value(TARGET_VALUE_PROPERTY)

    @property
    def is_on(self) -> bool | None:
        """Return a boolean for the state of the switch."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self._target_value is not None:
            await self._async_set_value(self._target_value, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self._target_value is not None:
            await self._async_set_value(self._target_value, False)


class ZWaveIndicatorSwitch(ZWaveSwitch):
    """Representation of a Z-Wave Indicator CC switch."""

    def __init__(
        self, config_entry: ZwaveJSConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the switch."""
        super().__init__(config_entry, driver, info)
        self._target_value = self.info.primary_value
        self._attr_name = self.generate_name(include_value_name=True)


class ZWaveBarrierEventSignalingSwitch(ZWaveBaseEntity, SwitchEntity):
    """Switch is used to turn on/off a barrier device's event signaling subsystem."""

    def __init__(
        self,
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveBarrierEventSignalingSwitch entity."""
        super().__init__(config_entry, driver, info)
        self._state: bool | None = None

        self._update_state()

        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)

    @callback
    def on_value_update(self) -> None:
        """Call when a watched value is added or updated."""
        self._update_state()

    @property
    def is_on(self) -> bool | None:
        """Return a boolean for the state of the switch."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_value(
            self.info.primary_value, BarrierEventSignalingSubsystemState.ON
        )
        # this value is not refreshed, so assume success
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_value(
            self.info.primary_value, BarrierEventSignalingSubsystemState.OFF
        )
        # this value is not refreshed, so assume success
        self._state = False
        self.async_write_ha_state()

    @callback
    def _update_state(self) -> None:
        self._state = None
        if self.info.primary_value.value is not None:
            self._state = (
                self.info.primary_value.value == BarrierEventSignalingSubsystemState.ON
            )


class ZWaveConfigParameterSwitch(ZWaveSwitch):
    """Representation of a Z-Wave config parameter switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, config_entry: ZwaveJSConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZWaveConfigParameterSwitch entity."""
        super().__init__(config_entry, driver, info)

        property_key_name = self.info.primary_value.property_key_name
        # Entity class attributes
        self._attr_name = self.generate_name(
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[property_key_name] if property_key_name else None,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_value(self.info.primary_value, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_value(self.info.primary_value, 0)

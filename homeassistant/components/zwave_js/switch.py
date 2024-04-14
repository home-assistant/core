"""Representation of Z-Wave switches."""

from __future__ import annotations

from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import TARGET_VALUE_PROPERTY
from zwave_js_server.const.command_class.barrier_operator import (
    BarrierEventSignalingSubsystemState,
)
from zwave_js_server.model.driver import Driver

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

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


class ZWaveSwitch(ZWaveBaseEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
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
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the switch."""
        super().__init__(config_entry, driver, info)
        self._target_value = self.info.primary_value
        self._attr_name = self.generate_name(include_value_name=True)


class ZWaveBarrierEventSignalingSwitch(ZWaveBaseEntity, SwitchEntity):
    """Switch is used to turn on/off a barrier device's event signaling subsystem."""

    def __init__(
        self,
        config_entry: ConfigEntry,
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
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
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

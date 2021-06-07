"""Representation of Z-Wave sensors."""
from __future__ import annotations

import logging
from typing import cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass, ConfigurationValueType
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .helpers import get_device_id

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Sensor."""
        entities: list[ZWaveBaseEntity] = []

        if info.platform_hint == "string_sensor":
            entities.append(ZWaveStringSensor(config_entry, client, info))
        elif info.platform_hint == "numeric_sensor":
            entities.append(ZWaveNumericSensor(config_entry, client, info))
        elif info.platform_hint == "list_sensor":
            entities.append(ZWaveListSensor(config_entry, client, info))
        elif info.platform_hint == "config_parameter":
            entities.append(ZWaveConfigParameterSensor(config_entry, client, info))
        else:
            LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.propertyname,
            )
            return

        async_add_entities(entities)

    @callback
    def async_add_node_status_sensor(node: ZwaveNode) -> None:
        """Add node status sensor."""
        async_add_entities([ZWaveNodeStatusSensor(config_entry, client, node)])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SENSOR_DOMAIN}",
            async_add_sensor,
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_node_status_sensor",
            async_add_node_status_sensor,
        )
    )


class ZwaveSensorBase(ZWaveBaseEntity, SensorEntity):
    """Basic Representation of a Z-Wave sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveSensorBase entity."""
        super().__init__(config_entry, client, info)

        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)
        self._attr_device_class = self._get_device_class()
        self._attr_state_class = self._get_state_class()
        self._attr_entity_registry_enabled_default = True
        # We hide some of the more advanced sensors by default to not overwhelm users
        if self.info.primary_value.command_class in [
            CommandClass.BASIC,
            CommandClass.CONFIGURATION,
            CommandClass.INDICATOR,
            CommandClass.NOTIFICATION,
        ]:
            self._attr_entity_registry_enabled_default = False

    def _get_device_class(self) -> str | None:
        """
        Get the device class of the sensor.

        This should be run once during initialization so we don't have to calculate
        this value on every state update.
        """
        if self.info.primary_value.command_class == CommandClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        if self.info.primary_value.command_class == CommandClass.METER:
            if self.info.primary_value.metadata.unit == "kWh":
                return DEVICE_CLASS_ENERGY
            return DEVICE_CLASS_POWER
        if isinstance(self.info.primary_value.property_, str):
            property_lower = self.info.primary_value.property_.lower()
            if "humidity" in property_lower:
                return DEVICE_CLASS_HUMIDITY
            if "temperature" in property_lower:
                return DEVICE_CLASS_TEMPERATURE
        if self.info.primary_value.metadata.unit == "W":
            return DEVICE_CLASS_POWER
        if self.info.primary_value.metadata.unit == "Lux":
            return DEVICE_CLASS_ILLUMINANCE
        return None

    def _get_state_class(self) -> str | None:
        """
        Get the state class of the sensor.

        This should be run once during initialization so we don't have to calculate
        this value on every state update.
        """
        if self.info.primary_value.command_class == CommandClass.BATTERY:
            return STATE_CLASS_MEASUREMENT
        if isinstance(self.info.primary_value.property_, str):
            property_lower = self.info.primary_value.property_.lower()
            if "humidity" in property_lower or "temperature" in property_lower:
                return STATE_CLASS_MEASUREMENT
        return None

    @property
    def force_update(self) -> bool:
        """Force updates."""
        return True


class ZWaveStringSensor(ZwaveSensorBase):
    """Representation of a Z-Wave String sensor."""

    @property
    def state(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        return str(self.info.primary_value.value)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        return str(self.info.primary_value.metadata.unit)


class ZWaveNumericSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveNumericSensor entity."""
        super().__init__(config_entry, client, info)

        # Entity class attributes
        if self.info.primary_value.command_class == CommandClass.BASIC:
            self._attr_name = self.generate_name(
                include_value_name=True,
                alternate_value_name=self.info.primary_value.command_class_name,
            )

    @property
    def state(self) -> float:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return 0
        return round(float(self.info.primary_value.value), 2)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        if self.info.primary_value.metadata.unit == "C":
            return TEMP_CELSIUS
        if self.info.primary_value.metadata.unit == "F":
            return TEMP_FAHRENHEIT

        return str(self.info.primary_value.metadata.unit)


class ZWaveListSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor with multiple states."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveListSensor entity."""
        super().__init__(config_entry, client, info)

        # Entity class attributes
        self._attr_name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
        )

    @property
    def state(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            str(self.info.primary_value.value)
            not in self.info.primary_value.metadata.states
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        # add the value's int value as property for multi-value (list) items
        return {"value": self.info.primary_value.value}


class ZWaveConfigParameterSensor(ZwaveSensorBase):
    """Representation of a Z-Wave config parameter sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveConfigParameterSensor entity."""
        super().__init__(config_entry, client, info)
        self._primary_value = cast(ConfigurationValue, self.info.primary_value)

        # Entity class attributes
        self._attr_name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
            name_suffix="Config Parameter",
        )

    @property
    def state(self) -> str | None:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        if (
            self._primary_value.configuration_value_type == ConfigurationValueType.RANGE
            or (
                not str(self.info.primary_value.value)
                in self.info.primary_value.metadata.states
            )
        ):
            return str(self.info.primary_value.value)
        return str(
            self.info.primary_value.metadata.states[str(self.info.primary_value.value)]
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device specific state attributes."""
        if self._primary_value.configuration_value_type == ConfigurationValueType.RANGE:
            return None
        # add the value's int value as property for multi-value (list) items
        return {"value": self.info.primary_value.value}


class ZWaveNodeStatusSensor(SensorEntity):
    """Representation of a node status sensor."""

    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, node: ZwaveNode
    ) -> None:
        """Initialize a generic Z-Wave device entity."""
        self.config_entry = config_entry
        self.client = client
        self.node = node
        name: str = (
            self.node.name
            or self.node.device_config.description
            or f"Node {self.node.node_id}"
        )
        # Entity class attributes
        self._attr_name = f"{name}: Node Status"
        self._attr_unique_id = (
            f"{self.client.driver.controller.home_id}.{node.node_id}.node_status"
        )
        # device is precreated in main handler
        self._attr_device_info = {
            "identifiers": {get_device_id(self.client, self.node)},
        }
        self._attr_state: str = node.status.name.lower()

    async def async_poll_value(self, _: bool) -> None:
        """Poll a value."""
        raise ValueError("There is no value to poll for this entity")

    def _status_changed(self, _: dict) -> None:
        """Call when status event is received."""
        self._attr_state = self.node.status.name.lower()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        # Add value_changed callbacks.
        for evt in ("wake up", "sleep", "dead", "alive"):
            self.async_on_remove(self.node.on(evt, self._status_changed))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.unique_id}_poll_value",
                self.async_poll_value,
            )
        )
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.client.connected and bool(self.node.ready)

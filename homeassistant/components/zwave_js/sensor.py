"""Representation of Z-Wave sensors."""
from __future__ import annotations

import logging
from typing import cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass, ConfigurationValueType
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DOMAIN as SENSOR_DOMAIN,
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

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SENSOR_DOMAIN}",
            async_add_sensor,
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
        self._name = self.generate_name(include_value_name=True)
        self._device_class = self._get_device_class()

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

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some of the more advanced sensors by default to not overwhelm users
        if self.info.primary_value.command_class in [
            CommandClass.BASIC,
            CommandClass.CONFIGURATION,
            CommandClass.INDICATOR,
            CommandClass.NOTIFICATION,
        ]:
            return False
        return True

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
        if self.info.primary_value.command_class == CommandClass.BASIC:
            self._name = self.generate_name(
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
        self._name = self.generate_name(
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
        self._name = self.generate_name(
            include_value_name=True,
            alternate_value_name=self.info.primary_value.property_name,
            additional_info=[self.info.primary_value.property_key_name],
            name_suffix="Config Parameter",
        )
        self._primary_value = cast(ConfigurationValue, self.info.primary_value)

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

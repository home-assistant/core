"""Representation of Z-Wave sensors."""

import logging
from typing import Callable, Dict, List, Optional

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Sensor."""
        entities: List[ZWaveBaseEntity] = []

        if info.platform_hint == "string_sensor":
            entities.append(ZWaveStringSensor(config_entry, client, info))
        elif info.platform_hint == "numeric_sensor":
            entities.append(ZWaveNumericSensor(config_entry, client, info))
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


class ZwaveSensorBase(ZWaveBaseEntity):
    """Basic Representation of a Z-Wave sensor."""

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        if self.info.primary_value.command_class == CommandClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        if self.info.primary_value.command_class == CommandClass.METER:
            if self.info.primary_value.property_key_name == "kWh_Consumed":
                return DEVICE_CLASS_ENERGY
            return DEVICE_CLASS_POWER
        if self.info.primary_value.property_ == "Air temperature":
            return DEVICE_CLASS_TEMPERATURE
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some of the more advanced sensors by default to not overwhelm users
        if self.info.primary_value.command_class in [
            CommandClass.BASIC,
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
    def state(self) -> Optional[str]:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return None
        return str(self.info.primary_value.value)

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        return str(self.info.primary_value.metadata.unit)


class ZWaveNumericSensor(ZwaveSensorBase):
    """Representation of a Z-Wave Numeric sensor."""

    @property
    def state(self) -> float:
        """Return state of the sensor."""
        if self.info.primary_value.value is None:
            return 0
        return round(float(self.info.primary_value.value), 2)

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return unit of measurement the value is expressed in."""
        if self.info.primary_value.metadata.unit is None:
            return None
        if self.info.primary_value.metadata.unit == "C":
            return TEMP_CELSIUS
        if self.info.primary_value.metadata.unit == "F":
            return TEMP_FAHRENHEIT

        return str(self.info.primary_value.metadata.unit)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, str]]:
        """Return the device specific state attributes."""
        if (
            self.info.primary_value.value is None
            or not self.info.primary_value.metadata.states
        ):
            return None
        # add the value's label as property for multi-value (list) items
        label = self.info.primary_value.metadata.states.get(
            self.info.primary_value.value
        ) or self.info.primary_value.metadata.states.get(
            str(self.info.primary_value.value)
        )
        return {"label": label}

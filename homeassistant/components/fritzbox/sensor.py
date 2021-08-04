"""Support for AVM FRITZ!SmartHome temperature sensor only devices."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from . import FritzBoxEntity
from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    CONF_COORDINATOR,
    DOMAIN as FRITZBOX_DOMAIN,
)
from .model import SensorExtraAttributes


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome sensor from ConfigEntry."""
    entities: list[FritzBoxEntity] = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if device.has_temperature_sensor and not device.has_thermostat:
            entities.append(
                FritzBoxTempSensor(
                    {
                        ATTR_NAME: f"{device.name} Temperature",
                        ATTR_ENTITY_ID: f"{device.ain}_temperature",
                        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                    },
                    coordinator,
                    ain,
                )
            )

        if device.battery_level is not None:
            entities.append(
                FritzBoxBatterySensor(
                    {
                        ATTR_NAME: f"{device.name} Battery",
                        ATTR_ENTITY_ID: f"{device.ain}_battery",
                        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                        ATTR_STATE_CLASS: None,
                    },
                    coordinator,
                    ain,
                )
            )

        if device.has_powermeter:
            entities.append(
                FritzBoxPowerSensor(
                    {
                        ATTR_NAME: f"{device.name} Power Consumption",
                        ATTR_ENTITY_ID: f"{device.ain}_power_consumption",
                        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
                        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                    },
                    coordinator,
                    ain,
                )
            )
            entities.append(
                FritzBoxEnergySensor(
                    {
                        ATTR_NAME: f"{device.name} Total Energy",
                        ATTR_ENTITY_ID: f"{device.ain}_total_energy",
                        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                    },
                    coordinator,
                    ain,
                )
            )

    async_add_entities(entities)


class FritzBoxBatterySensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome battery sensors."""

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self.device.battery_level  # type: ignore [no-any-return]


class FritzBoxPowerSensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome power consumption sensors."""

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        if power := self.device.power:
            return power / 1000  # type: ignore [no-any-return]
        return 0.0


class FritzBoxEnergySensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome total energy sensors."""

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        if energy := self.device.energy:
            return energy / 1000  # type: ignore [no-any-return]
        return 0.0

    @property
    def last_reset(self) -> datetime:
        """Return the time when the sensor was last reset, if any."""
        # device does not provide timestamp of initialization
        return utc_from_timestamp(0)


class FritzBoxTempSensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome temperature sensors."""

    @property
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self.device.temperature  # type: ignore [no-any-return]

    @property
    def extra_state_attributes(self) -> SensorExtraAttributes:
        """Return the state attributes of the device."""
        attrs: SensorExtraAttributes = {
            ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
            ATTR_STATE_LOCKED: self.device.lock,
        }
        return attrs

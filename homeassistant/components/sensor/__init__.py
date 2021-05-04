"""Component to interface with various sensors that can be monitored."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "sensor"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)
DEVICE_CLASSES = [
    DEVICE_CLASS_BATTERY,  # % of battery that is left
    DEVICE_CLASS_CO,  # ppm (parts per million) Carbon Monoxide gas concentration
    DEVICE_CLASS_CO2,  # ppm (parts per million) Carbon Dioxide gas concentration
    DEVICE_CLASS_CURRENT,  # current (A)
    DEVICE_CLASS_ENERGY,  # energy (kWh, Wh)
    DEVICE_CLASS_HUMIDITY,  # % of humidity in the air
    DEVICE_CLASS_ILLUMINANCE,  # current light level (lx/lm)
    DEVICE_CLASS_SIGNAL_STRENGTH,  # signal strength (dB/dBm)
    DEVICE_CLASS_TEMPERATURE,  # temperature (C/F)
    DEVICE_CLASS_TIMESTAMP,  # timestamp (ISO8601)
    DEVICE_CLASS_PRESSURE,  # pressure (hPa/mbar)
    DEVICE_CLASS_POWER,  # power (W/kW)
    DEVICE_CLASS_POWER_FACTOR,  # power factor (%)
    DEVICE_CLASS_VOLTAGE,  # voltage (V)
]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

# The state represents a measurement in present time
STATE_CLASS_MEASUREMENT = "measurement"

STATE_CLASSES = [STATE_CLASS_MEASUREMENT]

STATE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(STATE_CLASSES))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component = cast(EntityComponent, hass.data[DOMAIN])
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component = cast(EntityComponent, hass.data[DOMAIN])
    return await component.async_unload_entry(entry)


class SensorEntity(Entity):
    """Base class for sensor entities."""

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return None

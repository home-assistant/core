"""Sensor platform support for wiffi devices."""

import logging
from pathlib import Path

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import PRESSURE_MBAR, TEMP_CELSIUS

from .const import DOMAIN
from .entity_base import WiffiEntity
from .wiffi_strings import (
    WIFFI_UOM_DEGREE,
    WIFFI_UOM_LUX,
    WIFFI_UOM_MILLI_BAR,
    WIFFI_UOM_PERCENT,
    WIFFI_UOM_TEMP_CELSIUS,
)

_LOGGER = logging.getLogger(__name__)

# map to convert wiffi unit of measurements to common HA uom's
UOM_MAP = {
    WIFFI_UOM_DEGREE: "°",
    WIFFI_UOM_TEMP_CELSIUS: TEMP_CELSIUS,
    WIFFI_UOM_MILLI_BAR: PRESSURE_MBAR,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setup has been called
    during initialization of a new integration (= wiffi).
    """
    stem = Path(__file__).stem  # stem = filename without py
    hass.data[DOMAIN][config_entry.entry_id].async_add_entities[
        stem
    ] = async_add_entities


class NumberEntity(WiffiEntity):
    """Entity for wiffi metrics which have a number value."""

    def __init__(self, device_id, device_info, metric):
        """Initialize the entity."""
        WiffiEntity.__init__(self, device_id, device_info, metric)
        self._device_class = determine_device_class(metric)
        self._unit_of_measurement = convert_unit_of_measurement(
            metric.unit_of_measurement
        )
        self._value = metric.value
        self.reset_expiration_date()

    @property
    def device_class(self):
        """Return the automatically determined device class."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the value of the entity."""
        return self._value

    async def update_value(self, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._unit_of_measurement = convert_unit_of_measurement(
            metric.unit_of_measurement
        )
        self._value = metric.value
        if self.enabled:
            self.async_schedule_update_ha_state()


class StringEntity(WiffiEntity):
    """Entity for wiffi metrics which have a string value."""

    def __init__(self, device_id, device_info, metric):
        """Initialize the entity."""
        WiffiEntity.__init__(self, device_id, device_info, metric)
        self._value = metric.value
        self.reset_expiration_date()

    @property
    def state(self):
        """Return the value of the entity."""
        return self._value

    async def update_value(self, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._value = metric.value
        if self.enabled:
            self.async_schedule_update_ha_state()


def convert_unit_of_measurement(oum):
    """Convert german wiffi texts to common HA texts."""
    return UOM_MAP[oum] if oum in UOM_MAP else oum


def determine_device_class(metric):
    """Try to find best matching device class.

    Currently only units of measurements are used for the detection and
    therefore a dict with the uom as key could be used also. However, other
    the detection may be improved in the future using other fields as well,
    therefore a simple if/elsif chain is used here.
    """
    if metric.unit_of_measurement == WIFFI_UOM_TEMP_CELSIUS:
        return DEVICE_CLASS_TEMPERATURE
    if metric.unit_of_measurement == WIFFI_UOM_PERCENT:
        return DEVICE_CLASS_HUMIDITY
    if metric.unit_of_measurement == WIFFI_UOM_MILLI_BAR:
        return DEVICE_CLASS_PRESSURE
    if metric.unit_of_measurement == WIFFI_UOM_LUX:
        return DEVICE_CLASS_ILLUMINANCE
    return None

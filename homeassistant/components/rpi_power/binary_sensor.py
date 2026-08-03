"""Detect underruns and capped status from the Raspberry Pi Kernel.

Minimal Kernel needed is 4.14+
"""

import logging

from rpi_bad_power import UnderVoltage

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue

from . import RpiPowerConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_NORMALIZED = "Voltage normalized. Everything is working as intended."
DESCRIPTION_UNDER_VOLTAGE = (
    "Under-voltage was detected. Consider getting a uninterruptible power supply for"
    " your Raspberry Pi."
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RpiPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rpi_power binary sensor."""
    under_voltage = config_entry.runtime_data
    async_add_entities([RaspberryChargerBinarySensor(under_voltage)], True)


class RaspberryChargerBinarySensor(BinarySensorEntity):
    """Binary sensor representing the rpi power status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "rpi_power"
    _attr_has_entity_name = True
    _attr_unique_id = "rpi_power"  # only one sensor possible  # pylint: disable=home-assistant-entity-unique-id-redundant-domain

    def __init__(self, under_voltage: UnderVoltage) -> None:
        """Initialize the binary sensor."""
        self._under_voltage = under_voltage

        self._attr_device_info = DeviceInfo(
            manufacturer="Raspberry Pi",
            identifiers={(DOMAIN, "rpi_power")},
            name="Raspberry Pi",
        )

    def update(self) -> None:
        """Update the state."""
        value = self._under_voltage.get()
        if self._attr_is_on != value:
            if value:
                _LOGGER.warning(DESCRIPTION_UNDER_VOLTAGE)
                create_issue(
                    self.hass,
                    DOMAIN,
                    "under_voltage_detected",
                    is_fixable=True,
                    is_persistent=True,
                    severity=IssueSeverity.CRITICAL,
                    translation_key="under_voltage_detected",
                )
            else:
                _LOGGER.debug(DESCRIPTION_NORMALIZED)
            self._attr_is_on = value

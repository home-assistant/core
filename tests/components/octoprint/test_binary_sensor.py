"""The tests for Octoptint binary sensor module."""
import logging

from pyoctoprintapi import OctoprintPrinterInfo

from homeassistant.components.octoprint import binary_sensor as sensor
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def test_OctoPrintPrintingBinarySensor_properties(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {"printer": {}}
    test_sensor = sensor.OctoPrintPrintingBinarySensor(coordinator, "OctoPrint")
    assert "OctoPrint Printing" == test_sensor.name


def test_OctoPrintPrintingErrorBinarySensor_properties(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {"printer": {}}
    test_sensor = sensor.OctoPrintPrintingErrorBinarySensor(coordinator, "OctoPrint")
    assert "OctoPrint Printing Error" == test_sensor.name
    assert not test_sensor.device_class


def test_OctoPrintPrintingBinarySensor_is_on(hass):
    """Test the is_on property."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {
                        "printing": True,
                    },
                    "text": "Operational",
                },
                "temperature": [],
            }
        )
    }
    test_sensor = sensor.OctoPrintPrintingBinarySensor(coordinator, "OctoPrint")
    assert STATE_ON == test_sensor.state

    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {
                        "printing": False,
                    },
                    "text": "Operational",
                },
                "temperature": [],
            }
        )
    }
    assert STATE_OFF == test_sensor.state


def test_OctoPrintPrintingErrorBinarySensor_is_on(hass):
    """Test the is_on property."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {
                        "error": True,
                    },
                    "text": "Operational",
                },
                "temperature": [],
            }
        )
    }
    test_sensor = sensor.OctoPrintPrintingErrorBinarySensor(coordinator, "OctoPrint")
    assert STATE_ON == test_sensor.state

    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {
                        "error": False,
                    },
                    "text": "Operational",
                },
                "temperature": [],
            }
        )
    }
    assert STATE_OFF == test_sensor.state

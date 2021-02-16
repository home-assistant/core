"""The tests for Octoptint binary sensor module."""
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.components.octoprint import sensor
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def test_OctoPrintSensorBase_properties(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {"job": {}}
    test_sensor = sensor.OctoPrintSensorBase(coordinator, "OctoPrint", "type")
    assert "OctoPrint type" == test_sensor.name
    assert not test_sensor.device_class


def test_OctoPrintJobPercentageSensor(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "job": OctoprintJobInfo(
            {
                "job": {},
                "progress": {"completion": 50},
            }
        )
    }
    test_sensor = sensor.OctoPrintJobPercentageSensor(coordinator, "OctoPrint")
    assert "OctoPrint Job Percentage" == test_sensor.name
    assert 50 == test_sensor.state

    coordinator.data["job"]._raw["progress"]["completion"] = None
    assert 0 == test_sensor.state


def test_OctoPrintStatusSensor(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {},
                    "text": "Operational",
                },
                "temperature": [],
            }
        )
    }
    test_sensor = sensor.OctoPrintStatusSensor(coordinator, "OctoPrint")
    assert "OctoPrint Current State" == test_sensor.name
    assert "Operational" == test_sensor.state


def test_OctoPrintTimeElapsedSensor(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "job": OctoprintJobInfo(
            {
                "job": {},
                "progress": {"printTime": 5000},
            }
        )
    }
    test_sensor = sensor.OctoPrintTimeElapsedSensor(coordinator, "OctoPrint")
    assert "OctoPrint Time Elapsed" == test_sensor.name
    assert 5000 == test_sensor.state

    coordinator.data["job"]._raw["progress"]["printTime"] = None
    assert not test_sensor.state


def test_OctoPrintTemperatureSensor(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "printer": OctoprintPrinterInfo(
            {
                "state": {
                    "flags": {},
                    "text": "Operational",
                },
                "temperature": {"tool1": {"actual": 18.83136}},
            }
        )
    }
    test_sensor = sensor.OctoPrintTemperatureSensor(
        coordinator, "OctoPrint", "tool1", "actual"
    )
    assert "OctoPrint actual tool1 temp" == test_sensor.name
    assert 18.83 == test_sensor.state


def test_OctoPrintTimeRemainingSensor(hass):
    """Test the properties."""
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="octoprint-test")
    coordinator.data = {
        "job": OctoprintJobInfo(
            {
                "job": {},
                "progress": {"printTimeLeft": 5000},
            }
        )
    }
    test_sensor = sensor.OctoPrintTimeRemainingSensor(coordinator, "OctoPrint")
    assert "OctoPrint Time Remaining" == test_sensor.name
    assert 5000 == test_sensor.state

    coordinator.data["job"]._raw["progress"]["printTimeLeft"] = None
    assert not test_sensor.state

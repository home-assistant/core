"""Tests for the Bosch SHC sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Every device_helper bucket bosch_shc's platforms iterate over, defaulted to
# empty so a full component setup only ever creates the sensor entities under
# test here, regardless of what other platforms look for.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "shutter_controls",
        "thermostats",
        "wallthermostats",
        "twinguards",
        "smart_plugs",
        "light_switches_bsm",
        "smart_plugs_compact",
        "shutter_contacts",
        "shutter_contacts2",
        "motion_detectors",
        "smoke_detectors",
        "universal_switches",
        "water_leakage_detectors",
        "camera_eyes",
        "camera_360",
    )
}


def _named(name: str) -> SimpleNamespace:
    """Build a minimal enum-like object exposing only .name, as boschshcpy enums do."""
    return SimpleNamespace(name=name)


def _base_device(device_id: str, **extra: Any) -> SimpleNamespace:
    return SimpleNamespace(
        name="Test Device",
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_services=[],
        manufacturer="Bosch",
        device_model="TEST",
        status="AVAILABLE",
        deleted=False,
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
        **extra,
    )


def _thermostat_device(
    device_id: str = "hdm:HomeMaticIP:thermostat1",
    temperature: float = 21.5,
    position: int = 42,
    valvestate: str = "OK",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        temperature=temperature,
        position=position,
        valvestate=_named(valvestate),
    )


def _wallthermostat_device(
    device_id: str = "hdm:HomeMaticIP:wallthermostat1",
    temperature: float = 20.0,
    humidity: float = 45.0,
) -> SimpleNamespace:
    return _base_device(device_id, temperature=temperature, humidity=humidity)


def _twinguard_device(
    device_id: str = "hdm:HomeMaticIP:twinguard1",
    temperature: float = 22.0,
    humidity: float = 50.0,
    purity: float = 500.0,
    combined_rating: str = "GOOD",
    description: str = "Air quality is good",
    temperature_rating: str = "GOOD",
    humidity_rating: str = "GOOD",
    purity_rating: str = "GOOD",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        temperature=temperature,
        humidity=humidity,
        purity=purity,
        combined_rating=_named(combined_rating),
        description=description,
        temperature_rating=_named(temperature_rating),
        humidity_rating=_named(humidity_rating),
        purity_rating=_named(purity_rating),
    )


def _smart_plug_device(
    device_id: str = "hdm:HomeMaticIP:plug1",
    powerconsumption: float = 12.5,
    energyconsumption: float = 3000.0,
) -> SimpleNamespace:
    return _base_device(
        device_id,
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
    )


def _smart_plug_compact_device(
    device_id: str = "hdm:HomeMaticIP:plugcompact1",
    powerconsumption: float = 8.0,
    energyconsumption: float = 1500.0,
    communicationquality: str = "GOOD",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
        communicationquality=_named(communicationquality),
    )


async def _setup_sensor_integration(
    hass: HomeAssistant, **device_buckets: list[SimpleNamespace]
) -> MockConfigEntry:
    """Set up bosch_shc with the given device_helper buckets, via a mocked session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    mock_session.information.unique_id = "test-mac"
    mock_session.information.updateState.name = "UP_TO_DATE"
    mock_session.information.version = "2.0"
    mock_session.device_helper = SimpleNamespace(
        **{**_EMPTY_DEVICE_BUCKETS, **device_buckets}
    )

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession", return_value=mock_session
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_thermostat_creates_temperature_and_valve_sensors(
    hass: HomeAssistant,
) -> None:
    """A thermostats device yields a temperature sensor and a valve-tappet sensor."""
    device = _thermostat_device(temperature=21.5, position=42, valvestate="OK")
    await _setup_sensor_integration(hass, thermostats=[device])

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 2

    temperature_state = next(
        s for s in states if s.attributes.get("device_class") == "temperature"
    )
    assert float(temperature_state.state) == 21.5

    valve_state = next(s for s in states if s != temperature_state)
    assert float(valve_state.state) == 42
    assert valve_state.attributes["valve_tappet_state"] == "OK"


async def test_wallthermostat_creates_temperature_and_humidity_sensors(
    hass: HomeAssistant,
) -> None:
    """A wallthermostats device yields a temperature sensor and a humidity sensor."""
    device = _wallthermostat_device(temperature=20.0, humidity=45.0)
    await _setup_sensor_integration(hass, wallthermostats=[device])

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 2

    temperature_state = next(
        s for s in states if s.attributes.get("device_class") == "temperature"
    )
    assert float(temperature_state.state) == 20.0

    humidity_state = next(
        s for s in states if s.attributes.get("device_class") == "humidity"
    )
    assert float(humidity_state.state) == 45.0


async def test_twinguard_creates_seven_sensors(hass: HomeAssistant) -> None:
    """A twinguards device yields all 7 twinguard sensor types."""
    device = _twinguard_device(
        temperature=22.0,
        humidity=50.0,
        purity=500.0,
        combined_rating="GOOD",
        description="Air quality is good",
    )
    await _setup_sensor_integration(hass, twinguards=[device])

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 7

    air_quality_state = hass.states.get("sensor.test_device_air_quality")
    assert air_quality_state is not None
    assert air_quality_state.state == "GOOD"
    assert air_quality_state.attributes["rating_description"] == "Air quality is good"


@pytest.mark.parametrize(
    "bucket",
    [
        pytest.param("smart_plugs", id="smart_plugs"),
        pytest.param("light_switches_bsm", id="light_switches_bsm"),
    ],
)
async def test_smart_plug_creates_power_and_energy_sensors(
    hass: HomeAssistant, bucket: str
) -> None:
    """A smart_plugs or light_switches_bsm device yields a power + energy sensor (kWh)."""
    device = _smart_plug_device(powerconsumption=12.5, energyconsumption=3000.0)
    await _setup_sensor_integration(hass, **{bucket: [device]})

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 2

    power_state = next(s for s in states if s.attributes.get("device_class") == "power")
    assert float(power_state.state) == 12.5

    energy_state = next(
        s for s in states if s.attributes.get("device_class") == "energy"
    )
    assert float(energy_state.state) == 3.0


async def test_smart_plug_compact_creates_three_sensors(hass: HomeAssistant) -> None:
    """A smart_plugs_compact device yields power, energy, and communication-quality sensors."""
    device = _smart_plug_compact_device(communicationquality="GOOD")
    await _setup_sensor_integration(hass, smart_plugs_compact=[device])

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 3

    quality_state = hass.states.get("sensor.test_device_communication_quality")
    assert quality_state is not None
    assert quality_state.state == "GOOD"


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no sensor entities are created."""
    await _setup_sensor_integration(hass)

    assert hass.states.async_all(SENSOR_DOMAIN) == []

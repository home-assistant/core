"""Test the ADS sensor platform."""

import struct
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, async_run_past_first_update, setup_ads_platform

ADS_VAR = "GVL.temperature"
ENTITY_ID = "sensor.temperature"


@pytest.mark.parametrize(
    ("platform_config", "payload", "entity_id"),
    [
        pytest.param(
            {
                "adsvar": ADS_VAR,
                "name": "Temperature",
                "adstype": "int",
                "factor": 10,
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "°C",
            },
            struct.pack("<h", 215),
            ENTITY_ID,
            id="temperature",
        ),
        pytest.param(
            {"adsvar": ADS_VAR},
            struct.pack("<h", 42),
            "sensor.ads_sensor",
            id="defaults",
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ads_device: MockAdsDevice,
    snapshot: SnapshotAssertion,
    platform_config: dict[str, Any],
    payload: bytes,
    entity_id: str,
) -> None:
    """Test the sensor is created from YAML with the PLC's value."""
    mock_ads_device.values[ADS_VAR] = payload

    assert await setup_ads_platform(hass, SENSOR_DOMAIN, platform_config)

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


@pytest.mark.parametrize(
    ("adstype", "payload", "expected"),
    [
        pytest.param("bool", b"\x01", "True", id="bool"),
        pytest.param("byte", struct.pack("<B", 200), "200", id="byte"),
        pytest.param("usint", struct.pack("<B", 200), "200", id="usint"),
        pytest.param("sint", struct.pack("<b", -100), "-100", id="sint"),
        pytest.param("int", struct.pack("<h", -1000), "-1000", id="int"),
        pytest.param("uint", struct.pack("<H", 60000), "60000", id="uint"),
        pytest.param("word", struct.pack("<H", 60000), "60000", id="word"),
        pytest.param("dint", struct.pack("<i", -100000), "-100000", id="dint"),
        pytest.param("udint", struct.pack("<I", 100000), "100000", id="udint"),
        # Decoded as signed, so values from 2**31 up come out negative.
        pytest.param(
            "udint", struct.pack("<I", 3_000_000_000), "-1294967296", id="udint_high"
        ),
        pytest.param("dword", struct.pack("<I", 100000), "100000", id="dword"),
        pytest.param(
            "dword", struct.pack("<I", 3_000_000_000), "-1294967296", id="dword_high"
        ),
        pytest.param("real", struct.pack("<f", 21.5), "21.5", id="real"),
        pytest.param("lreal", struct.pack("<d", -0.125), "-0.125", id="lreal"),
    ],
)
async def test_decodes_the_plc_value(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    adstype: str,
    payload: bytes,
    expected: str,
) -> None:
    """Test the sensor decodes the value as its ADS type."""
    mock_ads_device.values[ADS_VAR] = payload

    assert await setup_ads_platform(
        hass,
        SENSOR_DOMAIN,
        {"adsvar": ADS_VAR, "name": "Temperature", "adstype": adstype},
    )

    assert hass.states.get(ENTITY_ID).state == expected


async def test_state_follows_the_plc(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test the sensor follows the values the PLC pushes, scaled by the factor."""
    mock_ads_device.values[ADS_VAR] = struct.pack("<h", 215)
    assert await setup_ads_platform(
        hass, SENSOR_DOMAIN, {"adsvar": ADS_VAR, "name": "Temperature", "factor": 10}
    )
    assert hass.states.get(ENTITY_ID).state == "21.5"

    await mock_ads_device.async_push(hass, ADS_VAR, struct.pack("<h", -40))
    assert hass.states.get(ENTITY_ID).state == "-4.0"


async def test_invalid_config(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test a sensor with an unsupported ADS type is not created."""
    await setup_ads_platform(
        hass,
        SENSOR_DOMAIN,
        {"adsvar": ADS_VAR, "name": "Temperature", "adstype": "string"},
    )

    assert hass.states.get(ENTITY_ID) is None


# The division by zero happens in the pyads callback thread.
@pytest.mark.filterwarnings(
    "ignore:Exception in thread:pytest.PytestUnhandledThreadExceptionWarning"
)
async def test_zero_factor(hass: HomeAssistant, mock_ads_device: MockAdsDevice) -> None:
    """Test a factor of zero is accepted, and the sensor never gets a value."""
    mock_ads_device.values[ADS_VAR] = struct.pack("<h", 215)

    assert await async_run_past_first_update(
        hass,
        setup_ads_platform(
            hass,
            SENSOR_DOMAIN,
            {"adsvar": ADS_VAR, "name": "Temperature", "factor": 0},
        ),
    )

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

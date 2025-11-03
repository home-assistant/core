"""Tests for the Bbox sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.bbox.sensor import PLATFORM_SCHEMA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_MONITORED_VARIABLES, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_sensor_entities_created(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test that sensor entities are created when integration is set up."""
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    # Verify all 6 sensor types are created
    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 6


@pytest.mark.parametrize(
    ("sensor_type", "expected_value"),
    [
        ("down_max_bandwidth", 100000.0),
        ("up_max_bandwidth", 50000.0),
        ("current_down_bandwidth", 50000.0),
        ("current_up_bandwidth", 25000.0),
        ("number_of_reboots", 5),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
    sensor_type: str,
    expected_value: float,
) -> None:
    """Test sensor values for different sensor types."""
    sensor_config[SENSOR_DOMAIN][CONF_MONITORED_VARIABLES] = [sensor_type]
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 1

    state = states[0]
    assert state.state == str(expected_value)


async def test_uptime_sensor(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test uptime sensor."""
    sensor_config[SENSOR_DOMAIN][CONF_MONITORED_VARIABLES] = ["uptime"]
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 1

    state = states[0]
    assert state.state is not None
    assert state.attributes.get("attribution") == "Powered by Bouygues Telecom"
    assert state.attributes.get("device_class") == "timestamp"


async def test_sensor_attributes(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test sensor attributes."""
    sensor_config[SENSOR_DOMAIN][CONF_MONITORED_VARIABLES] = ["down_max_bandwidth"]
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 1

    state = states[0]
    assert state.attributes.get("attribution") == "Powered by Bouygues Telecom"
    assert state.attributes.get("device_class") == "data_rate"
    assert state.attributes.get("unit_of_measurement") == "Mbit/s"


async def test_setup_all_sensors(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test setup with all sensor types."""
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    # Verify all 6 sensor types are created
    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 6


async def test_setup_api_failure(
    hass: HomeAssistant,
    sensor_config: dict,
    mock_bbox_api: MagicMock,
) -> None:
    """Test setup with API failure."""
    # Mock API failure
    mock_bbox_api.get_ip_stats.side_effect = Exception("API Error")
    mock_bbox_api.get_bbox_info.side_effect = Exception("API Error")

    # Setup should succeed but no entities created when API fails during setup
    await async_setup_component(hass, SENSOR_DOMAIN, sensor_config)
    await hass.async_block_till_done()

    # No entities should be created when API fails during setup
    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 0


async def test_async_setup_component(
    hass: HomeAssistant,
    mock_bbox_api: MagicMock,
) -> None:
    """Test async setup component with sensor platform."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "bbox",
                    "monitored_variables": [
                        "down_max_bandwidth",
                        "up_max_bandwidth",
                        "current_down_bandwidth",
                        "current_up_bandwidth",
                        "uptime",
                        "number_of_reboots",
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 6


async def test_platform_schema() -> None:
    """Test platform schema validation."""
    config = {
        CONF_MONITORED_VARIABLES: [
            "down_max_bandwidth",
            "up_max_bandwidth",
            "current_down_bandwidth",
            "current_up_bandwidth",
            "number_of_reboots",
            "uptime",
        ],
        CONF_NAME: "Test Bbox",
        "platform": "bbox",
    }

    validated = PLATFORM_SCHEMA(config)
    assert validated[CONF_MONITORED_VARIABLES] == config[CONF_MONITORED_VARIABLES]
    assert validated[CONF_NAME] == "Test Bbox"

    # Test with default name
    config = {
        CONF_MONITORED_VARIABLES: ["down_max_bandwidth"],
        "platform": "bbox",
    }

    validated = PLATFORM_SCHEMA(config)
    assert validated[CONF_NAME] == "Bbox"

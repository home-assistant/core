"""Tests for rainbird sensor platform."""


import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CONFIG_ENTRY_DATA, RAIN_DELAY, RAIN_DELAY_OFF, ComponentSetup


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.parametrize(
    ("rain_delay_response", "expected_state"),
    [(RAIN_DELAY, "16"), (RAIN_DELAY_OFF, "0")],
)
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry: er.EntityRegistry,
    expected_state: str,
) -> None:
    """Test sensor platform."""

    assert await setup_integration()

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.state == expected_state
    assert raindelay.attributes == {
        "friendly_name": "Rain Bird Controller Raindelay",
        "icon": "mdi:water-off",
    }

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert entity_entry
    assert entity_entry.unique_id == "1263613994342-raindelay"


@pytest.mark.parametrize(
    ("config_entry_unique_id", "config_entry_data"),
    [
        # Config entry setup without a unique id since it had no serial number
        (
            None,
            {
                **CONFIG_ENTRY_DATA,
                "serial_number": 0,
            },
        ),
        # Legacy case for old config entries with serial number 0 preserves old behavior
        (
            "0",
            {
                **CONFIG_ENTRY_DATA,
                "serial_number": 0,
            },
        ),
    ],
)
async def test_sensor_no_unique_id(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry: er.EntityRegistry,
    config_entry_unique_id: str | None,
) -> None:
    """Test sensor platform with no unique id."""

    assert await setup_integration()

    raindelay = hass.states.get("sensor.rain_bird_controller_raindelay")
    assert raindelay is not None
    assert raindelay.attributes.get("friendly_name") == "Rain Bird Controller Raindelay"

    entity_entry = entity_registry.async_get("sensor.rain_bird_controller_raindelay")
    assert (entity_entry is None) == (config_entry_unique_id is None)

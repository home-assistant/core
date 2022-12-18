"""The tests for the generic_hygrostat config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.generic_hygrostat.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

EXAMPLE_SLIM_CONFIG = {
    "name": "Bedroom",
    "humidifier": "switch.humidifier_plug",
    "target_sensor": "sensor.outside_humidity",
}


EXAMPLE_FULL_CONFIG = {
    "name": "Bedroom",
    "humidifier": "switch.humidifier_plug",
    "target_sensor": "sensor.outside_humidity",
    "min_humidity": 30,
    "max_humidity": 70,
    "target_humidity": 50,
    "dry_tolerance": 3,
    "wet_tolerance": 0,
    "device_class": "humidifier",
    "min_cycle_duration": 1,
    "keep_alive": 3,
    "initial_state": True,
    "away_humidity": 35,
    "away_fixed": True,
    "sensor_stale_duration": 15,
}


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test that the config form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry_slim(hass: HomeAssistant) -> None:
    """Test that the example slim config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=EXAMPLE_SLIM_CONFIG
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["options"] == EXAMPLE_SLIM_CONFIG


async def test_create_entry_full(hass: HomeAssistant) -> None:
    """Test that the example full config entry is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=EXAMPLE_FULL_CONFIG
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["options"] == EXAMPLE_FULL_CONFIG

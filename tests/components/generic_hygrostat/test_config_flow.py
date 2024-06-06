"""Test the generic hygrostat config flow."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant import config_entries
from homeassistant.components.generic_hygrostat import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_mock_service


async def test_config_flow(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result == snapshot(name="init", exclude=props("data_schema"))

    with patch(
        "homeassistant.components.generic_hygrostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My dehumidifier",
                "dry_tolerance": 2,
                "wet_tolerance": 4,
                "humidifier": "switch.run",
                "target_sensor": "sensor.humidity",
                "device_class": "dehumidifier",
                "away_humidity": 35,
                "initial_state": True,
            },
        )
        await hass.async_block_till_done()

    assert result == snapshot(name="create")
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert result == snapshot(name="options")
    assert config_entry.title == "My dehumidifier"


async def test_options(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test reconfiguring."""

    turn_off_calls = async_mock_service(hass, "homeassistant", "turn_off")
    turn_on_calls = async_mock_service(hass, "homeassistant", "turn_on")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "away_humidity": 35.0,
            "device_class": "dehumidifier",
            "dry_tolerance": 2.0,
            "humidifier": "switch.run",
            "initial_state": True,
            "name": "test",
            "target_sensor": "sensor.humidity",
            "wet_tolerance": 4.0,
        },
        title="My dehumidifier",
    )
    config_entry.add_to_hass(hass)

    # start with a humidity less than max, and a switch that is on
    hass.states.async_set(
        "sensor.humidity",
        "10",
        {"unit_of_measurement": "%", "device_class": "humidity"},
    )
    hass.states.async_set("switch.run", "on")

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # will turn off on start, since humidity is less than max
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 1

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result == snapshot(name="init", exclude=props("data_schema", "handler"))

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "dry_tolerance": 2,
            "wet_tolerance": 4,
            "humidifier": "switch.run",
            "target_sensor": "sensor.humidity",
            "device_class": "dehumidifier",
            "initial_state": True,
        },
    )
    assert result == snapshot(name="create_entry", exclude=props("handler"))

    assert config_entry.data == {}
    assert config_entry.options == snapshot(name="options", exclude=props("handler"))

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check no new entity was created
    assert len(hass.states.async_all()) == 3

    await hass.async_block_till_done()

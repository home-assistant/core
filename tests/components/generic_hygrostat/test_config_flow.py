"""Test the generic hygrostat config flow."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.generic_hygrostat import (
    CONF_AWAY_HUMIDITY,
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_INITIAL_STATE,
    CONF_NAME,
    CONF_SENSOR,
    CONF_WET_TOLERANCE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_mock_service


async def test_config_flow(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result == snapshot(name="init", exclude=props("data_schema"))

    with patch(
        "homeassistant.components.generic_hygrostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My dehumidifier",
                CONF_DRY_TOLERANCE: 2,
                CONF_WET_TOLERANCE: 4,
                CONF_HUMIDIFIER: "switch.run",
                CONF_SENSOR: "sensor.humidity",
                CONF_DEVICE_CLASS: "dehumidifier",
                CONF_AWAY_HUMIDITY: 35,
                CONF_INITIAL_STATE: True,
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
            CONF_AWAY_HUMIDITY: 35.0,
            CONF_DEVICE_CLASS: "dehumidifier",
            CONF_DRY_TOLERANCE: 2.0,
            CONF_HUMIDIFIER: "switch.run",
            CONF_INITIAL_STATE: True,
            CONF_NAME: "My dehumidifier",
            CONF_SENSOR: "sensor.humidity",
            CONF_WET_TOLERANCE: 4.0,
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

    # check that it is setup
    await hass.async_block_till_done()
    assert hass.states.get("humidifier.my_dehumidifier") == snapshot(name="with_away")

    # remove away feature
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DRY_TOLERANCE: 2,
            CONF_WET_TOLERANCE: 4,
            CONF_HUMIDIFIER: "switch.run",
            CONF_SENSOR: "sensor.humidity",
            CONF_DEVICE_CLASS: "dehumidifier",
            CONF_INITIAL_STATE: True,
        },
    )
    assert result == snapshot(name="create_entry", exclude=props("handler"))

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    assert hass.states.get("humidifier.my_dehumidifier") == snapshot(
        name="without_away"
    )

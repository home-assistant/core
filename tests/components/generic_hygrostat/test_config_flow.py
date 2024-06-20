"""Test the generic hygrostat config flow."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.generic_hygrostat import (
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_NAME,
    CONF_SENSOR,
    CONF_WET_TOLERANCE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SNAPSHOT_FLOW_PROPS = props("type", "title", "result", "error")


async def test_config_flow(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result == snapshot(name="init", include=SNAPSHOT_FLOW_PROPS)

    with patch(
        "homeassistant.components.generic_hygrostat.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My hygrostat",
                CONF_DRY_TOLERANCE: 2,
                CONF_WET_TOLERANCE: 4,
                CONF_HUMIDIFIER: "switch.run",
                CONF_SENSOR: "sensor.humidity",
                CONF_DEVICE_CLASS: "dehumidifier",
            },
        )
        await hass.async_block_till_done()

    assert result == snapshot(name="create", include=SNAPSHOT_FLOW_PROPS)
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.title == "My hygrostat"


async def test_options(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test reconfiguring."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_DEVICE_CLASS: "dehumidifier",
            CONF_DRY_TOLERANCE: 2.0,
            CONF_HUMIDIFIER: "switch.run",
            CONF_NAME: "My hygrostat",
            CONF_SENSOR: "sensor.humidity",
            CONF_WET_TOLERANCE: 4.0,
        },
        title="My hygrostat",
    )
    config_entry.add_to_hass(hass)

    # set some initial values
    hass.states.async_set(
        "sensor.humidity",
        "10",
        {"unit_of_measurement": "%", "device_class": "humidity"},
    )
    hass.states.async_set("switch.run", "on")

    # check that it is setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("humidifier.my_hygrostat") == snapshot(name="dehumidifier")

    # switch to humidifier
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result == snapshot(name="init", include=SNAPSHOT_FLOW_PROPS)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DRY_TOLERANCE: 2,
            CONF_WET_TOLERANCE: 4,
            CONF_HUMIDIFIER: "switch.run",
            CONF_SENSOR: "sensor.humidity",
            CONF_DEVICE_CLASS: "humidifier",
        },
    )
    assert result == snapshot(name="create_entry", include=SNAPSHOT_FLOW_PROPS)

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    assert hass.states.get("humidifier.my_hygrostat") == snapshot(name="humidifier")

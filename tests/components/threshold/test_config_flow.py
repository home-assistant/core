"""Test the Threshold config flow."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.threshold.const import DOMAIN
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value
from tests.typing import WebSocketGenerator


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    input_sensor = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.threshold.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": input_sensor,
                "lower": -2,
                "upper": 0.0,
                "name": "My threshold sensor",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My threshold sensor"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": input_sensor,
        "hysteresis": 0.0,
        "lower": -2.0,
        "name": "My threshold sensor",
        "upper": 0.0,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "hysteresis": 0.0,
        "lower": -2.0,
        "name": "My threshold sensor",
        "upper": 0.0,
    }
    assert config_entry.title == "My threshold sensor"


@pytest.mark.parametrize(("extra_input_data", "error"), [({}, "need_lower_upper")])
async def test_fail(hass: HomeAssistant, extra_input_data, error) -> None:
    """Test not providing lower or upper limit fails."""
    input_sensor = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "entity_id": input_sensor,
            "name": "My threshold sensor",
            **extra_input_data,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    input_sensor = "sensor.input"
    hass.states.async_set(input_sensor, "10")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor,
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "My threshold",
            "upper": None,
        },
        title="My threshold",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "hysteresis") == 0.0
    assert get_schema_suggested_value(schema, "lower") == -2.0
    assert get_schema_suggested_value(schema, "upper") is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_id": input_sensor,
            "hysteresis": 0.0,
            "upper": 20.0,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entity_id": input_sensor,
        "hysteresis": 0.0,
        "lower": None,
        "name": "My threshold",
        "upper": 20.0,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "hysteresis": 0.0,
        "lower": None,
        "name": "My threshold",
        "upper": 20.0,
    }
    assert config_entry.title == "My threshold"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 2

    # Check the state of the entity has changed as expected
    state = hass.states.get("binary_sensor.my_threshold")
    assert state.state == "off"
    assert state.attributes["type"] == "upper"


@pytest.mark.parametrize(
    "user_input",
    [
        (
            {
                "name": "Test Sensor",
                "entity_id": "sensor.test_monitored",
                "hysteresis": 0.0,
                "lower": 20.0,
            }
        ),
        (
            {
                "name": "Test Sensor",
                "entity_id": "sensor.test_monitored",
                "hysteresis": 0.0,
            }
        ),
        (
            {
                "name": "",
                "entity_id": "",
                "hysteresis": 0.0,
                "lower": 20.0,
            }
        ),
    ],
    ids=("success", "missing_upper_lower", "missing_entity_id"),
)
async def test_config_flow_preview_success(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    user_input: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    # add state for the tests
    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["preview"] == "threshold"

    await client.send_json_auto_id(
        {
            "type": "threshold/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == snapshot
    assert len(hass.states.async_all()) == 1


async def test_options_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the options flow preview."""
    client = await hass_ws_client(hass)

    # add state for the tests
    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.test_monitored",
            "hysteresis": 0.0,
            "lower": 20.0,
            "name": "Test Sensor",
            "upper": None,
        },
        title="Test Sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "threshold"

    await client.send_json_auto_id(
        {
            "type": "threshold/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                "name": "Test Sensor",
                "entity_id": "sensor.test_monitored",
                "hysteresis": 0.0,
                "lower": 20.0,
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == snapshot
    assert len(hass.states.async_all()) == 2


async def test_options_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.test_monitored",
            "hysteresis": 0.0,
            "lower": 20.0,
            "name": "Test Sensor",
            "upper": None,
        },
        title="Test Sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "threshold"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "threshold/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                "name": "Test Sensor",
                "entity_id": "sensor.test_monitored",
                "hysteresis": 0.0,
                "lower": 20.0,
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "home_assistant_error",
        "message": "Config entry not found",
    }

"""Test the Mold indicator config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.mold_indicator.const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_form_sensor(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form for sensor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_INDOOR_TEMP: "sensor.indoor_temp",
        CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
        CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
        CONF_CALIBRATION_FACTOR: 2.0,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 3.0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_INDOOR_TEMP: "sensor.indoor_temp",
        CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
        CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
        CONF_CALIBRATION_FACTOR: 3.0,
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    # 3 input entities + resulting mold indicator sensor
    assert len(hass.states.async_all()) == 4

    state = hass.states.get("sensor.mold_indicator")
    assert state is not None


async def test_calibration_factor_not_zero(hass: HomeAssistant) -> None:
    """Test calibration factor is not zero."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 0.0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "calibration_is_zero"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 1.0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_INDOOR_TEMP: "sensor.indoor_temp",
        CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
        CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
        CONF_CALIBRATION_FACTOR: 1.0,
    }


async def test_entry_already_exist(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test abort when entry already exist."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "user_input",
    [
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_INDOOR_TEMP: "sensor.indoor_temp",
                CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
                CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
                CONF_CALIBRATION_FACTOR: 2.0,
            }
        ),
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_INDOOR_TEMP: "sensor.indoor_temp",
                CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
                CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            }
        ),
        (
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_INDOOR_TEMP: "sensor.indoor_temp",
                CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
                CONF_CALIBRATION_FACTOR: 2.0,
            }
        ),
    ],
    ids=("success", "missing_calibration_factor", "missing_humidity_entity"),
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
        "sensor.indoor_temp",
        23,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.indoor_humidity",
        50,
        {CONF_UNIT_OF_MEASUREMENT: "%"},
    )
    hass.states.async_set(
        "sensor.outdoor_temp",
        16,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["preview"] == "mold_indicator"

    await client.send_json_auto_id(
        {
            "type": "mold_indicator/start_preview",
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
    assert len(hass.states.async_all()) == 3


async def test_options_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the options flow preview."""
    client = await hass_ws_client(hass)

    # add state for the tests
    hass.states.async_set(
        "sensor.indoor_temp",
        23,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.indoor_humidity",
        50,
        {CONF_UNIT_OF_MEASUREMENT: "%"},
    )
    hass.states.async_set(
        "sensor.outdoor_temp",
        16,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="Test Sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "mold_indicator"

    await client.send_json_auto_id(
        {
            "type": "mold_indicator/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_NAME: DEFAULT_NAME,
                CONF_INDOOR_TEMP: "sensor.indoor_temp",
                CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
                CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
                CONF_CALIBRATION_FACTOR: 2.0,
            },
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == snapshot
    assert len(hass.states.async_all()) == 4


async def test_options_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    hass.states.async_set(
        "sensor.indoor_temp",
        23,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.indoor_humidity",
        50,
        {CONF_UNIT_OF_MEASUREMENT: "%"},
    )
    hass.states.async_set(
        "sensor.outdoor_temp",
        16,
        {CONF_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="Test Sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "mold_indicator"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "mold_indicator/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {
                CONF_NAME: DEFAULT_NAME,
                CONF_INDOOR_TEMP: "sensor.indoor_temp",
                CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
                CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
                CONF_CALIBRATION_FACTOR: 2.0,
            },
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "home_assistant_error",
        "message": "Config entry not found",
    }

"""Test the Mold indicator config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.mold_indicator.const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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

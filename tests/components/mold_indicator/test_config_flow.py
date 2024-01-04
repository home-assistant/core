"""Test the mold_indicator config flow."""
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.mold_indicator import config_flow
from homeassistant.components.mold_indicator.const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_DATA_STEP = {
    CONF_NAME: DEFAULT_NAME,
    CONF_INDOOR_HUMIDITY: "sensor.test_indoor_humidity_entity_id",
    CONF_INDOOR_TEMP: "sensor.test_indoor_temperature_entity_id",
    CONF_OUTDOOR_TEMP: "sensor.test_outdoor_temperature_entity_id",
    CONF_CALIBRATION_FACTOR: 1.0,
}


async def test_flow_user_init_data_success(hass: HomeAssistant) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["handler"] == "mold_indicator"
    assert result["data_schema"] == config_flow.DATA_SCHEMA

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Mold Indicator"

    assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_STEP,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


MOCK_DATA_IMPORT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_INDOOR_HUMIDITY: "sensor.test_indoor_humidity_entity_id",
    CONF_INDOOR_TEMP: "sensor.test_indoor_temperature_entity_id",
    CONF_OUTDOOR_TEMP: "sensor.test_outdoor_temperature_entity_id",
    CONF_CALIBRATION_FACTOR: 1.0,
}


async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA_IMPORT,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_DATA_IMPORT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test we abort import when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_IMPORT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA_IMPORT,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

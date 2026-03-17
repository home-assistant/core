"""Test the photoptimizer config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.photoptimizer.const import (
    CONF_API_KEY,
    CONF_AZIMUTH,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_EFFICIENCY_ROUND_TRIP,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_SOC_RESERVE_PERCENT,
    CONF_CURRENT_CONSUMPTION_ENTITY,
    CONF_CURRENT_SOLAR_PRODUCTION_ENTITY,
    CONF_DECLINATION,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_EMHASS_TOKEN,
    CONF_EMHASS_URL,
    CONF_GRID_POWER_ENTITY,
    CONF_HORIZON_HOURS,
    CONF_KWP,
    CONF_LATITUDE,
    CONF_LOAD_FORECAST_ENTITY,
    CONF_LONGITUDE,
    CONF_PRICE_INCLUDE_VAT,
    CONF_RESOLUTION,
    CONF_WEAR_COST_PER_KWH,
    DEFAULT_EMHASS_URL,
    DOMAIN,
)
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_config_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the complete user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "electricity_price"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ELECTRICITY_PRICE_ENTITY: "sensor.spot_price",
            CONF_PRICE_INCLUDE_VAT: True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pv_forecast"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LATITUDE: 49.5962536,
            CONF_LONGITUDE: 18.3395664,
            CONF_AZIMUTH: 124,
            CONF_DECLINATION: 40,
            CONF_KWP: 6.44,
            CONF_API_KEY: "forecast-solar-key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "load_forecast"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LOAD_FORECAST_ENTITY: "sensor.load_forecast"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "inverter"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CURRENT_SOLAR_PRODUCTION_ENTITY: "sensor.pv_now",
            CONF_CURRENT_CONSUMPTION_ENTITY: "sensor.load_now",
            CONF_GRID_POWER_ENTITY: "sensor.grid_now",
            CONF_BATTERY_SOC_ENTITY: "sensor.battery_soc",
            CONF_BATTERY_CAPACITY_KWH: 10.0,
            CONF_BATTERY_SOC_RESERVE_PERCENT: 20.0,
            CONF_BATTERY_EFFICIENCY_ROUND_TRIP: 95.0,
            CONF_WEAR_COST_PER_KWH: 0.1,
            CONF_EMHASS_URL: "http://192.168.1.104:5000",
            CONF_EMHASS_TOKEN: "emhass-token",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Photoptimizer"
    assert result["data"][CONF_HORIZON_HOURS] == 24
    assert result["data"][CONF_RESOLUTION] == "hourly"
    assert result["data"][CONF_ELECTRICITY_PRICE_ENTITY] == "sensor.spot_price"
    assert result["data"][CONF_EMHASS_URL] == "http://192.168.1.104:5000"
    assert len(mock_setup_entry.mock_calls) == 1


def get_suggested(schema: dict, key: str) -> str | None:
    """Get suggested value for key in voluptuous schema."""
    for schema_key in schema:
        if schema_key == key:
            if (
                schema_key.description is None
                or "suggested_value" not in schema_key.description
            ):
                return None
            return schema_key.description["suggested_value"]
    raise KeyError(f"Key `{key}` is missing from schema")


async def test_reconfigure_updates_emhass_connection(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test reconfigure flow updates EMHASS URL and token."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Photoptimizer",
        unique_id="49.5962536_18.3395664_6.44",
        data={
            CONF_HORIZON_HOURS: 24,
            CONF_RESOLUTION: "hourly",
            CONF_ELECTRICITY_PRICE_ENTITY: "sensor.spot_price",
            CONF_PRICE_INCLUDE_VAT: True,
            CONF_LATITUDE: 49.5962536,
            CONF_LONGITUDE: 18.3395664,
            CONF_AZIMUTH: 124,
            CONF_DECLINATION: 40,
            CONF_KWP: 6.44,
            CONF_CURRENT_SOLAR_PRODUCTION_ENTITY: "sensor.pv_now",
            CONF_CURRENT_CONSUMPTION_ENTITY: "sensor.load_now",
            CONF_GRID_POWER_ENTITY: "sensor.grid_now",
            CONF_BATTERY_SOC_ENTITY: "sensor.battery_soc",
            CONF_BATTERY_CAPACITY_KWH: 10.0,
            CONF_BATTERY_SOC_RESERVE_PERCENT: 20.0,
            CONF_BATTERY_EFFICIENCY_ROUND_TRIP: 95.0,
            CONF_WEAR_COST_PER_KWH: 0.1,
            CONF_EMHASS_URL: DEFAULT_EMHASS_URL,
            CONF_EMHASS_TOKEN: "old-token",
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    schema = result["data_schema"].schema
    assert get_suggested(schema, CONF_EMHASS_URL) == DEFAULT_EMHASS_URL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMHASS_URL: "http://192.168.1.200:5000",
            CONF_EMHASS_TOKEN: "new-token",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_EMHASS_URL] == "http://192.168.1.200:5000"
    assert config_entry.data[CONF_EMHASS_TOKEN] == "new-token"

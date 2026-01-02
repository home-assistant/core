"""Test for the weather entity of the IRM KMI integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2023-12-28T15:30:00+01:00")
async def test_weather_nl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api_nl: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test weather with forecast from the Netherland."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "forecast_type",
    ["daily", "hourly"],
)
@pytest.mark.freeze_time("2025-09-22T15:30:00+01:00")
async def test_forecast_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_irm_kmi_api_nl: AsyncMock,
    mock_config_entry: MockConfigEntry,
    forecast_type: str,
) -> None:
    """Test multiple forecast."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            ATTR_ENTITY_ID: "weather.home",
            "type": forecast_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.freeze_time("2024-01-21T14:15:00+01:00")
@pytest.mark.parametrize(
    "forecast_type",
    ["daily", "hourly"],
)
async def test_weather_higher_temp_at_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api_high_low_temp: AsyncMock,
    forecast_type: str,
) -> None:
    """Test that the templow is always lower than temperature, even when API returns the opposite."""
    # Test case for https://github.com/jdejaegh/irm-kmi-ha/issues/8
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {
            ATTR_ENTITY_ID: "weather.home",
            "type": forecast_type,
        },
        blocking=True,
        return_response=True,
    )
    for forecast in response["weather.home"]["forecast"]:
        assert (
            forecast.get("native_temperature") is None
            or forecast.get("native_templow") is None
            or forecast["native_temperature"] >= forecast["native_templow"]
        )

"""Tests for the London Air sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.london_air.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor reports the authority air quality band."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton_air_quality")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["sites"] == 2
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    data = state.attributes["data"]
    assert len(data) == 2
    assert data[0]["site_code"] == "ME2"
    assert data[0]["site_name"] == "Merton Road"
    assert data[0]["pollutants"][0]["code"] == "PM10"
    assert data[0]["pollutants"][0]["summary"] == "PM10 is Low"


async def test_sensor_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    api_payload: dict[str, Any],
) -> None:
    """Test the sensor becomes unavailable when a refresh fails."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=api_payload)
    mock_session.get.return_value = response

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.merton_air_quality")
    assert state is not None
    assert state.state == "unavailable"


async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """Test setup retries when the API is unavailable."""
    mock_session.get.return_value = MagicMock(
        raise_for_status=MagicMock(
            side_effect=ClientConnectorError(Mock(), OSError("test"))
        )
    )

    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

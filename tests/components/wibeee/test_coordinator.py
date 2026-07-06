"""Tests for Wibeee coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock
from xml.etree.ElementTree import ParseError as XMLParseError

import pytest

from homeassistant.components.wibeee.coordinator import WibeeeCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test coordinator returns the fetched data on success."""
    coordinator = WibeeeCoordinator(
        hass, mock_wibeee_api, config_entry=mock_config_entry, name="Wibeee 2233"
    )

    data = await coordinator._async_update_data()

    assert data == {
        "fase1": {"vrms": "230.5", "p_activa": "277"},
        "fase4": {"vrms": "230.5", "p_activa": "277"},
    }


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test coordinator update failure."""
    coordinator = WibeeeCoordinator(
        hass, mock_wibeee_api, config_entry=mock_config_entry, name="Wibeee 2233"
    )
    # Must be an exception that the coordinator catches (TimeoutError, ClientError, etc)
    mock_wibeee_api.async_fetch_sensors_data.side_effect = TimeoutError("Fetch failed")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_xml_parse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test coordinator translates XMLParseError into UpdateFailed."""
    coordinator = WibeeeCoordinator(
        hass, mock_wibeee_api, config_entry=mock_config_entry, name="Wibeee 2233"
    )
    mock_wibeee_api.async_fetch_sensors_data.side_effect = XMLParseError("bad xml")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> None:
    """Test coordinator handles no data received."""
    coordinator = WibeeeCoordinator(
        hass, mock_wibeee_api, config_entry=mock_config_entry, name="Wibeee 2233"
    )
    mock_wibeee_api.async_fetch_sensors_data.return_value = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

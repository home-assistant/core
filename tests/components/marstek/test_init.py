"""Tests for the Marstek integration."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import create_mock_udp_client

from tests.common import MockConfigEntry


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the async_setup function."""
    mock_client = create_mock_udp_client()

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert result is True
        assert DOMAIN in hass.data
        assert "udp_client" in hass.data[DOMAIN]

        # Verify services are registered
        assert hass.services.has_service(DOMAIN, "charge")
        assert hass.services.has_service(DOMAIN, "discharge")
        assert hass.services.has_service(DOMAIN, "stop")


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    with patch(
        "homeassistant.components.marstek.sensor.MarstekUDPClient",
        return_value=mock_client,
    ):
        # Mock the UDP client in hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["udp_client"] = mock_client

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_service_charge(hass: HomeAssistant) -> None:
    """Test the charge service."""
    mock_client = create_mock_udp_client()
    mock_client.send_request.return_value = {
        "id": 1,
        "result": {"mode": "Manual", "ongrid_power": -1300},
    }

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        # Setup component
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert result is True

        # Call service
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {CONF_HOST: "192.168.1.100", "power": 1300},
            blocking=True,
        )

        # Verify pause/resume were called
        assert mock_client.pause_polling.called
        assert mock_client.resume_polling.called


async def test_service_discharge(hass: HomeAssistant) -> None:
    """Test the discharge service."""
    mock_client = create_mock_udp_client()
    mock_client.send_request.return_value = {
        "id": 1,
        "result": {"mode": "Manual", "ongrid_power": 800},
    }

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert result is True

        await hass.services.async_call(
            DOMAIN,
            "discharge",
            {CONF_HOST: "192.168.1.100", "power": 800},
            blocking=True,
        )

        assert mock_client.pause_polling.called
        assert mock_client.resume_polling.called


async def test_service_stop(hass: HomeAssistant) -> None:
    """Test the stop service."""
    mock_client = create_mock_udp_client()
    mock_client.send_request.return_value = {
        "id": 1,
        "result": {"mode": "Manual", "ongrid_power": 0},
    }

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        result = await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert result is True

        await hass.services.async_call(
            DOMAIN,
            "stop",
            {CONF_HOST: "192.168.1.100"},
            blocking=True,
        )

        assert mock_client.pause_polling.called
        assert mock_client.resume_polling.called

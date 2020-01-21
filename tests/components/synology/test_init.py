"""Tests for the Synology component initialization."""
from asynctest import patch
import requests

from homeassistant.components import synology
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.setup import async_setup_component


async def test_empty_config(hass):
    """Test that component skips initialization if config is empty."""

    assert await async_setup_component(hass, synology.DOMAIN, {})
    await hass.async_block_till_done()

    assert synology.DOMAIN_DATA not in hass.data


async def test_platform_failed_init_synology_error(hass):
    """Test that component fails to initialize if failed to create Synology client."""

    with patch(
        "homeassistant.components.synology.SurveillanceStation"
    ) as mock_surveillance_station:
        mock_surveillance_station.side_effect = requests.exceptions.RequestException()

        assert not await async_setup_component(
            hass,
            synology.DOMAIN,
            {
                "synology": {
                    CONF_URL: "http://localhost",
                    CONF_USERNAME: "test",
                    CONF_PASSWORD: "password",
                    CONF_NAME: "test_name",
                    CONF_VERIFY_SSL: "True",
                }
            },
        )
        await hass.async_block_till_done()

        assert mock_surveillance_station.called

        assert synology.DOMAIN_DATA not in hass.data


async def test_platform_initialized(hass):
    """Test that component initializes with success."""

    with patch(
        "homeassistant.components.synology.SurveillanceStation"
    ) as mock_surveillance_station:
        assert await async_setup_component(
            hass,
            synology.DOMAIN,
            {
                "synology": {
                    CONF_URL: "http://localhost",
                    CONF_USERNAME: "test",
                    CONF_PASSWORD: "password",
                    CONF_NAME: "test_name",
                    CONF_VERIFY_SSL: "True",
                }
            },
        )
        await hass.async_block_till_done()

        assert mock_surveillance_station.called

        data = hass.data[synology.DOMAIN_DATA]
        assert data is not None
        assert len(data) == 3

        assert synology.DATA_SURVEILLANCE_CLIENT in data

        assert synology.DATA_VERIFY_SSL in data
        assert data[synology.DATA_VERIFY_SSL]

        assert synology.DATA_NAME in data
        assert "test_name" == data[synology.DATA_NAME]

"""Tests for ZoneMinder YAML configuration validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST, create_mock_zm_client

CONF_PATH_ZMS = "path_zms"


@pytest.fixture
def mock_client_patch():
    """Patch ZoneMinder client for config tests."""
    client = create_mock_zm_client()
    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ) as mock_cls:
        yield mock_cls, client


async def test_valid_minimal_config(hass: HomeAssistant, mock_client_patch) -> None:
    """Test valid minimal configuration with only required host."""
    mock_cls, _ = mock_client_patch
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    mock_cls.assert_called_once()


async def test_valid_full_config(hass: HomeAssistant, mock_client_patch) -> None:
    """Test valid full configuration with all optional fields."""
    mock_cls, _ = mock_client_patch
    config = {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
                CONF_PATH: "/zm/",
                CONF_PATH_ZMS: "/zm/cgi-bin/nph-zms",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
            }
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    mock_cls.assert_called_once()


async def test_valid_multi_server_config(
    hass: HomeAssistant, mock_client_patch, multi_server_config
) -> None:
    """Test valid multi-server configuration."""
    mock_cls, _ = mock_client_patch

    assert await async_setup_component(hass, DOMAIN, multi_server_config)
    await hass.async_block_till_done()

    assert mock_cls.call_count == 2


async def test_valid_ssl_config(
    hass: HomeAssistant, mock_client_patch, ssl_config
) -> None:
    """Test valid SSL configuration."""
    mock_cls, _ = mock_client_patch

    assert await async_setup_component(hass, DOMAIN, ssl_config)
    await hass.async_block_till_done()

    # Verify https prefix was used
    call_args = mock_cls.call_args
    assert call_args[0][0] == f"https://{MOCK_HOST}"


async def test_valid_no_auth_config(
    hass: HomeAssistant, mock_client_patch, no_auth_config
) -> None:
    """Test valid config without authentication credentials."""
    mock_cls, _ = mock_client_patch

    assert await async_setup_component(hass, DOMAIN, no_auth_config)
    await hass.async_block_till_done()

    call_args = mock_cls.call_args
    # Username and password should be None
    assert call_args[0][1] is None
    assert call_args[0][2] is None


async def test_config_defaults_applied(hass: HomeAssistant, mock_client_patch) -> None:
    """Test that default values are applied for optional fields."""
    mock_cls, _ = mock_client_patch
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    call_args = mock_cls.call_args
    # Default: http (no SSL)
    assert call_args[0][0] == f"http://{MOCK_HOST}"
    # Default path
    assert call_args[0][3] == "/zm/"
    # Default path_zms
    assert call_args[0][4] == "/zm/cgi-bin/nph-zms"
    # Default verify_ssl
    assert call_args[0][5] is True


async def test_invalid_config_missing_host(hass: HomeAssistant) -> None:
    """Test that config without host is rejected."""
    config: dict = {DOMAIN: [{}]}

    result = await async_setup_component(hass, DOMAIN, config)
    # Config validation should reject this - component won't set up
    assert not result or DOMAIN not in hass.data


async def test_invalid_config_bad_ssl_type(hass: HomeAssistant) -> None:
    """Test that non-boolean ssl value is rejected."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST, CONF_SSL: "not_bool"}]}

    result = await async_setup_component(hass, DOMAIN, config)
    assert not result or DOMAIN not in hass.data

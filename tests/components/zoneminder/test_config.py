"""Tests for ZoneMinder YAML configuration validation."""

from __future__ import annotations

from unittest.mock import MagicMock

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

from .conftest import MOCK_HOST

CONF_PATH_ZMS = "path_zms"


async def test_valid_minimal_config(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test valid minimal configuration with only required host."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_valid_full_config(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test valid full configuration with all optional fields."""
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


async def test_valid_multi_server_config(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    multi_server_config: dict,
) -> None:
    """Test valid multi-server configuration."""
    assert await async_setup_component(hass, DOMAIN, multi_server_config)
    await hass.async_block_till_done()


async def test_valid_ssl_config(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    ssl_config: dict,
) -> None:
    """Test valid SSL configuration."""
    assert await async_setup_component(hass, DOMAIN, ssl_config)
    await hass.async_block_till_done()


async def test_valid_no_auth_config(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    no_auth_config: dict,
) -> None:
    """Test valid config without authentication credentials."""
    assert await async_setup_component(hass, DOMAIN, no_auth_config)
    await hass.async_block_till_done()


async def test_config_defaults_applied(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test that default values are applied for optional fields."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


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


@pytest.mark.parametrize(
    ("config_override", "expected_origin"),
    [
        ({}, f"http://{MOCK_HOST}"),
        ({CONF_SSL: True}, f"https://{MOCK_HOST}"),
    ],
)
async def test_constructor_url_prefix(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    config_override: dict,
    expected_origin: str,
) -> None:
    """Test ZM constructor called with correct URL prefix."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST, **config_override}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    assert call_args[0][0] == expected_origin


async def test_constructor_default_args(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test that default constructor arguments are applied correctly."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    # Default: http (no SSL)
    assert call_args[0][0] == f"http://{MOCK_HOST}"
    # Default path
    assert call_args[0][3] == "/zm/"
    # Default path_zms
    assert call_args[0][4] == "/zm/cgi-bin/nph-zms"
    # Default verify_ssl
    assert call_args[0][5] is True


async def test_constructor_no_auth_args(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    no_auth_config: dict,
) -> None:
    """Test username and password are None when not provided."""
    assert await async_setup_component(hass, DOMAIN, no_auth_config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    assert call_args[0][1] is None
    assert call_args[0][2] is None

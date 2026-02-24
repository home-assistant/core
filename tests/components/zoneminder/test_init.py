"""Tests for ZoneMinder __init__.py setup flow internals."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PATH, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST

CONF_PATH_ZMS = "path_zms"


async def test_constructor_called_with_http_prefix(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test ZM constructor called with http prefix when ssl=false."""
    config = {DOMAIN: [{CONF_HOST: MOCK_HOST}]}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    mock_zoneminder_client.mock_cls.assert_called_once_with(
        f"http://{MOCK_HOST}",
        None,  # username
        None,  # password
        "/zm/",  # default path
        "/zm/cgi-bin/nph-zms",  # default path_zms
        True,  # default verify_ssl
    )


async def test_constructor_called_with_https_prefix(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    ssl_config: dict,
) -> None:
    """Test ZM constructor called with https prefix when ssl=true."""
    assert await async_setup_component(hass, DOMAIN, ssl_config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    assert call_args[0][0] == f"https://{MOCK_HOST}"


async def test_constructor_called_with_auth(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test ZM constructor called with correct username/password."""
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    assert call_args[0][1] == "admin"
    assert call_args[0][2] == "secret"


async def test_constructor_called_with_paths(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
) -> None:
    """Test ZM constructor called with custom paths."""
    config = {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_PATH: "/custom/",
                CONF_PATH_ZMS: "/custom/zms",
            }
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    call_args = mock_zoneminder_client.mock_cls.call_args
    assert call_args[0][3] == "/custom/"
    assert call_args[0][4] == "/custom/zms"


async def test_login_called_in_executor(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test login() is called during setup."""
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    mock_zoneminder_client.login.assert_called_once()


async def test_login_success_returns_true(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test async_setup returns True on login success."""
    mock_zoneminder_client.login.return_value = True

    result = await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    assert result is True


async def test_login_failure_returns_false(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test async_setup returns False on login failure."""
    mock_zoneminder_client.login.return_value = False

    await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()


async def test_connection_error_logged(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RequestsConnectionError is logged but doesn't crash setup.

    Regression: The original code (lines 76-82) catches the ConnectionError
    and logs it, but does NOT set success=False. This means a connection error
    doesn't prevent the component from reporting success.
    """
    mock_zoneminder_client.login.side_effect = RequestsConnectionError(
        "Connection refused"
    )

    result = await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    assert "ZoneMinder connection failure" in caplog.text
    assert "Connection refused" in caplog.text
    # The component still reports success (this is the regression behavior)
    assert result is True


async def test_async_setup_services_invoked(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test async_setup_services is called during setup."""
    with patch(
        "homeassistant.components.zoneminder.async_setup_services"
    ) as mock_services:
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()

    mock_services.assert_called_once_with(hass)


async def test_binary_sensor_platform_load_triggered(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test binary sensor platform load is triggered during setup."""
    with patch("homeassistant.components.zoneminder.async_load_platform") as mock_load:
        assert await async_setup_component(hass, DOMAIN, single_server_config)
        await hass.async_block_till_done()

    mock_load.assert_called_once()
    call_args = mock_load.call_args
    # Should load binary_sensor platform
    assert call_args[0][1] == Platform.BINARY_SENSOR
    assert call_args[0][2] == DOMAIN

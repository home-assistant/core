"""Test UniFi Controller."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.unifi.const import (
    CONF_CONTROLLER,
    CONF_SITE_ID,
    UNIFI_CONFIG,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.components.unifi import controller, errors

from tests.common import mock_coro

CONTROLLER_SITES = {"site1": {"desc": "nice name", "name": "site", "role": "admin"}}

CONTROLLER_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 1234,
    CONF_SITE_ID: "site",
    CONF_VERIFY_SSL: True,
}

ENTRY_CONFIG = {CONF_CONTROLLER: CONTROLLER_DATA}


async def test_controller_setup():
    """Successful setup."""
    hass = Mock()
    hass.data = {UNIFI_CONFIG: {}}
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.sites.return_value = mock_coro(CONTROLLER_SITES)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, "get_controller", return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.api is api
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 2
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == (
        entry,
        "device_tracker",
    )
    assert hass.config_entries.async_forward_entry_setup.mock_calls[1][1] == (
        entry,
        "switch",
    )


async def test_controller_host():
    """Config entry host and controller host are the same."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    assert unifi_controller.host == CONTROLLER_DATA[CONF_HOST]


async def test_controller_site():
    """Config entry site and controller site are the same."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    assert unifi_controller.site == CONTROLLER_DATA[CONF_SITE_ID]


async def test_controller_mac():
    """Test that it is possible to identify controller mac."""
    hass = Mock()
    hass.data = {UNIFI_CONFIG: {}}
    entry = Mock()
    entry.data = ENTRY_CONFIG
    client = Mock()
    client.ip = "1.2.3.4"
    client.mac = "00:11:22:33:44:55"
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.clients = {"client1": client}
    api.sites.return_value = mock_coro(CONTROLLER_SITES)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, "get_controller", return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.mac == "00:11:22:33:44:55"


async def test_controller_no_mac():
    """Test that it works to not find the controllers mac."""
    hass = Mock()
    hass.data = {UNIFI_CONFIG: {}}
    entry = Mock()
    entry.data = ENTRY_CONFIG
    client = Mock()
    client.ip = "5.6.7.8"
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.clients = {"client1": client}
    api.sites.return_value = mock_coro(CONTROLLER_SITES)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, "get_controller", return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.mac is None


async def test_controller_not_accessible():
    """Retry to login gets scheduled when connection fails."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(
        controller, "get_controller", side_effect=errors.CannotConnect
    ), pytest.raises(ConfigEntryNotReady):
        await unifi_controller.async_setup()


async def test_controller_unknown_error():
    """Unknown errors are handled."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, "get_controller", side_effect=Exception):
        assert await unifi_controller.async_setup() is False

    assert not hass.helpers.event.async_call_later.mock_calls


async def test_reset_if_entry_had_wrong_auth():
    """Calling reset when the entry contains wrong auth."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(
        controller, "get_controller", side_effect=errors.AuthenticationRequired
    ):
        assert await unifi_controller.async_setup() is False

    assert not hass.async_add_job.mock_calls

    assert await unifi_controller.async_reset()


async def test_reset_unloads_entry_if_setup():
    """Calling reset when the entry has been setup."""
    hass = Mock()
    hass.data = {UNIFI_CONFIG: {}}
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.sites.return_value = mock_coro(CONTROLLER_SITES)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, "get_controller", return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 2

    hass.config_entries.async_forward_entry_unload.return_value = mock_coro(True)
    assert await unifi_controller.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 2


async def test_get_controller(hass):
    """Successful call."""
    with patch("aiounifi.Controller.login", return_value=mock_coro()):
        assert await controller.get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_verify_ssl_false(hass):
    """Successful call with verify ssl set to false."""
    controller_data = dict(CONTROLLER_DATA)
    controller_data[CONF_VERIFY_SSL] = False
    with patch("aiounifi.Controller.login", return_value=mock_coro()):
        assert await controller.get_controller(hass, **controller_data)


async def test_get_controller_login_failed(hass):
    """Check that get_controller can handle a failed login."""
    import aiounifi

    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.Unauthorized):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.AuthenticationRequired:
            pass
        assert result is None


async def test_get_controller_controller_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    import aiounifi

    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.RequestError):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.CannotConnect:
            pass
        assert result is None


async def test_get_controller_unknown_error(hass):
    """Check that get_controller can handle unkown errors."""
    import aiounifi

    result = None
    with patch("aiounifi.Controller.login", side_effect=aiounifi.AiounifiException):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.AuthenticationRequired:
            pass
        assert result is None

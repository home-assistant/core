"""Test UniFi Controller."""
from unittest.mock import Mock, patch

from homeassistant.components import unifi
from homeassistant.components.unifi import controller, errors

from tests.common import mock_coro

CONTROLLER_DATA = {
    unifi.CONF_HOST: '1.2.3.4',
    unifi.CONF_USERNAME: 'username',
    unifi.CONF_PASSWORD: 'password',
    unifi.CONF_PORT: 1234,
    unifi.CONF_SITE_ID: 'site',
    unifi.CONF_VERIFY_SSL: True
}

ENTRY_CONFIG = {
    unifi.CONF_CONTROLLER: CONTROLLER_DATA,
    unifi.CONF_POE_CONTROL: True
    }


async def test_controller_setup():
    """Successful setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.api is api
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'switch')


async def test_controller_host():
    """Config entry host and controller host are the same."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    assert unifi_controller.host == '1.2.3.4'


async def test_controller_mac():
    """Test that it is possible to identify controller mac."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    client = Mock()
    client.ip = '1.2.3.4'
    client.mac = '00:11:22:33:44:55'
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.clients = {'client1': client}

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.mac == '00:11:22:33:44:55'


async def test_controller_no_mac():
    """Test that it works to not find the controllers mac."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    client = Mock()
    client.ip = '5.6.7.8'
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.clients = {'client1': client}

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      return_value=mock_coro(api)):
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

    with patch.object(controller, 'get_controller',
                      side_effect=errors.CannotConnect):
        assert await unifi_controller.async_setup() is False

    assert len(hass.helpers.event.async_call_later.mock_calls) == 1
    # Assert we are going to wait 2 seconds
    assert hass.helpers.event.async_call_later.mock_calls[0][1][0] == 2


async def test_controller_unknown_error():
    """Unknown errors are handled."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', side_effect=Exception):
        assert await unifi_controller.async_setup() is False

    assert not hass.helpers.event.async_call_later.mock_calls


async def test_reset_cancels_retry_setup():
    """Resetting a controller while we're waiting to retry setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      side_effect=errors.CannotConnect):
        assert await unifi_controller.async_setup() is False

    mock_call_later = hass.helpers.event.async_call_later

    assert len(mock_call_later.mock_calls) == 1

    assert await unifi_controller.async_reset()

    assert len(mock_call_later.mock_calls) == 2
    assert len(mock_call_later.return_value.mock_calls) == 1


async def test_reset_if_entry_had_wrong_auth():
    """Calling reset when the entry contains wrong auth."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      side_effect=errors.AuthenticationRequired):
        assert await unifi_controller.async_setup() is False

    assert not hass.async_add_job.mock_calls

    assert await unifi_controller.async_reset()


async def test_reset_unloads_entry_if_setup():
    """Calling reset when the entry has been setup."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    assert await unifi_controller.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 1


async def test_reset_unloads_entry_without_poe_control():
    """Calling reset while the entry has been setup."""
    hass = Mock()
    entry = Mock()
    entry.data = dict(ENTRY_CONFIG)
    entry.data[unifi.CONF_POE_CONTROL] = False
    api = Mock()
    api.initialize.return_value = mock_coro(True)

    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert not hass.config_entries.async_forward_entry_setup.mock_calls

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    assert await unifi_controller.async_reset()

    assert not hass.config_entries.async_forward_entry_unload.mock_calls


async def test_get_controller(hass):
    """Successful call."""
    with patch('aiounifi.Controller.login', return_value=mock_coro()):
        assert await controller.get_controller(hass, **CONTROLLER_DATA)


async def test_get_controller_verify_ssl_false(hass):
    """Successful call with verify ssl set to false."""
    controller_data = dict(CONTROLLER_DATA)
    controller_data[unifi.CONF_VERIFY_SSL] = False
    with patch('aiounifi.Controller.login', return_value=mock_coro()):
        assert await controller.get_controller(hass, **controller_data)


async def test_get_controller_login_failed(hass):
    """Check that get_controller can handle a failed login."""
    import aiounifi
    result = None
    with patch('aiounifi.Controller.login', side_effect=aiounifi.Unauthorized):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.AuthenticationRequired:
            pass
        assert result is None


async def test_get_controller_controller_unavailable(hass):
    """Check that get_controller can handle controller being unavailable."""
    import aiounifi
    result = None
    with patch('aiounifi.Controller.login',
               side_effect=aiounifi.RequestError):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.CannotConnect:
            pass
        assert result is None


async def test_get_controller_unknown_error(hass):
    """Check that get_controller can handle unkown errors."""
    import aiounifi
    result = None
    with patch('aiounifi.Controller.login',
               side_effect=aiounifi.AiounifiException):
        try:
            result = await controller.get_controller(hass, **CONTROLLER_DATA)
        except errors.AuthenticationRequired:
            pass
        assert result is None

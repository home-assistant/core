"""Test UniFi Controller."""
from unittest.mock import Mock, patch

from homeassistant.components import unifi
from homeassistant.components.unifi import controller, errors

from tests.common import mock_coro


async def test_controller_setup():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.api is api
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'switch')


async def test_controller_host():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    assert unifi_controller.host == '1.2.3.4'


async def test_controller_mac():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    client = Mock()
    client.ip = '1.2.3.4'
    client.mac = '00:11:22:33:44:55'
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    api.clients = {'client1': client}
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert unifi_controller.mac == '00:11:22:33:44:55'


async def test_controller_not_accessible():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      side_effect=errors.CannotConnect):
        assert await unifi_controller.async_setup() is False

    assert len(hass.helpers.event.async_call_later.mock_calls) == 1
    # Assert we are going to wait 2 seconds
    assert hass.helpers.event.async_call_later.mock_calls[0][1][0] == 2


async def test_controller_unknown_error():
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', side_effect=Exception):
        assert await unifi_controller.async_setup() is False

    assert not hass.helpers.event.async_call_later.mock_calls


async def test_reset_cancels_retry_setup():
    """Test resetting a bridge while we're waiting to retry setup."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
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
    """Test calling reset when the entry contained wrong auth."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller',
                      side_effect=errors.AuthenticationRequired):
        assert await unifi_controller.async_setup() is False

    assert not hass.async_add_job.mock_calls

    assert await unifi_controller.async_reset()


async def test_reset_unloads_entry_if_setup():
    """Test calling reset while the entry has been setup."""
    hass = Mock()
    entry = Mock()
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 1

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    assert await unifi_controller.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 1


async def test_reset_unloads_entry_without_poe_control():
    """Test calling reset while the entry has been setup."""
    hass = Mock()
    entry = Mock()
    api = Mock()
    api.initialize.return_value = mock_coro(True)
    entry.data = {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'site',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: False
    }
    unifi_controller = controller.UniFiController(hass, entry)

    with patch.object(controller, 'get_controller', return_value=mock_coro(api)):
        assert await unifi_controller.async_setup() is True

    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 0

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    assert await unifi_controller.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 0

"""Test UniFi setup process."""
from unittest.mock import Mock, patch

from homeassistant.components import unifi
from homeassistant.setup import async_setup_component

from tests.common import mock_coro, MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a bridge."""
    assert await async_setup_component(hass, unifi.DOMAIN, {}) is True
    assert unifi.DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(domain=unifi.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
            'site': 'default',
            'verify_ssl': True
        },
        'poe_control': True
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(unifi, 'UniFiController') as mock_controller, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_controller.return_value.async_setup.return_value = mock_coro(True)
        mock_controller.return_value.mac = '00:11:22:33:44:55'
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.mock_calls) == 2
    p_hass, p_entry = mock_controller.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry

    assert len(mock_registry.mock_calls) == 1
    assert mock_registry.mock_calls[0][2] == {
        'config_entry_id': entry.entry_id,
        'connections': {
            ('mac', '00:11:22:33:44:55')
        },
        'manufacturer': 'Ubiquiti',
        'model': "UniFi Controller",
        'name': "UniFi Controller",
    }


async def test_controller_fail_setup(hass):
    """Test that a failed setup still stores controller."""
    entry = MockConfigEntry(domain=unifi.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
            'site': 'default',
            'verify_ssl': True
        },
        'poe_control': True
    })
    entry.add_to_hass(hass)

    with patch.object(unifi, 'UniFiController') as mock_cntrlr:
        mock_cntrlr.return_value.async_setup.return_value = mock_coro(False)
        assert await unifi.async_setup_entry(hass, entry) is False

    controller_id = unifi.CONTROLLER_ID.format(
        host='0.0.0.0', site='default'
    )
    assert controller_id in hass.data[unifi.DOMAIN]


async def test_controller_no_mac(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(domain=unifi.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
            'site': 'default',
            'verify_ssl': True
        },
        'poe_control': True
    })
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch.object(unifi, 'UniFiController') as mock_controller, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(mock_registry)):
        mock_controller.return_value.async_setup.return_value = mock_coro(True)
        mock_controller.return_value.mac = None
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.mock_calls) == 2

    assert len(mock_registry.mock_calls) == 0


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=unifi.DOMAIN, data={
        'controller': {
            'host': '0.0.0.0',
            'username': 'user',
            'password': 'pass',
            'port': 80,
            'site': 'default',
            'verify_ssl': True
        },
        'poe_control': True
    })
    entry.add_to_hass(hass)

    with patch.object(unifi, 'UniFiController') as mock_controller, \
        patch('homeassistant.helpers.device_registry.async_get_registry',
              return_value=mock_coro(Mock())):
        mock_controller.return_value.async_setup.return_value = mock_coro(True)
        mock_controller.return_value.mac = '00:11:22:33:44:55'
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.return_value.mock_calls) == 1

    mock_controller.return_value.async_reset.return_value = mock_coro(True)
    assert await unifi.async_unload_entry(hass, entry)
    assert len(mock_controller.return_value.async_reset.mock_calls) == 1
    assert hass.data[unifi.DOMAIN] == {}


async def test_flow_works(hass, aioclient_mock):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    with patch('aiounifi.Controller') as mock_controller:
        def mock_constructor(host, username, password, port, site, websession):
            """Fake the controller constructor."""
            mock_controller.host = host
            mock_controller.username = username
            mock_controller.password = password
            mock_controller.port = port
            mock_controller.site = site
            return mock_controller

        mock_controller.side_effect = mock_constructor
        mock_controller.login.return_value = mock_coro()
        mock_controller.sites.return_value = mock_coro({
            'site1': {'name': 'default', 'role': 'admin', 'desc': 'site name'}
        })

        await flow.async_step_user(user_input={
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_VERIFY_SSL: True
        })

        result = await flow.async_step_site(user_input={})

    assert mock_controller.host == '1.2.3.4'
    assert len(mock_controller.login.mock_calls) == 1
    assert len(mock_controller.sites.mock_calls) == 1

    assert result['type'] == 'create_entry'
    assert result['title'] == 'site name'
    assert result['data'] == {
        unifi.CONF_CONTROLLER: {
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_SITE_ID: 'default',
            unifi.CONF_VERIFY_SSL: True
        },
        unifi.CONF_POE_CONTROL: True
    }


async def test_controller_multiple_sites(hass):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    flow.config = {
        unifi.CONF_HOST: '1.2.3.4',
        unifi.CONF_USERNAME: 'username',
        unifi.CONF_PASSWORD: 'password',
    }
    flow.sites = {
        'site1': {
            'name': 'default', 'role': 'admin', 'desc': 'site name'
        },
        'site2': {
            'name': 'site2', 'role': 'admin', 'desc': 'site2 name'
        }
    }

    result = await flow.async_step_site()

    assert result['type'] == 'form'
    assert result['step_id'] == 'site'

    assert result['data_schema']({'site': 'site name'})
    assert result['data_schema']({'site': 'site2 name'})


async def test_controller_site_already_configured(hass):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    entry = MockConfigEntry(domain=unifi.DOMAIN, data={
        'controller': {
            'host': '1.2.3.4',
            'site': 'default',
        }
    })
    entry.add_to_hass(hass)

    flow.config = {
        unifi.CONF_HOST: '1.2.3.4',
        unifi.CONF_USERNAME: 'username',
        unifi.CONF_PASSWORD: 'password',
    }
    flow.desc = 'site name'
    flow.sites = {
        'site1': {
            'name': 'default', 'role': 'admin', 'desc': 'site name'
        }
    }

    result = await flow.async_step_site()

    assert result['type'] == 'abort'


async def test_user_permissions_low(hass, aioclient_mock):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    with patch('aiounifi.Controller') as mock_controller:
        def mock_constructor(host, username, password, port, site, websession):
            """Fake the controller constructor."""
            mock_controller.host = host
            mock_controller.username = username
            mock_controller.password = password
            mock_controller.port = port
            mock_controller.site = site
            return mock_controller

        mock_controller.side_effect = mock_constructor
        mock_controller.login.return_value = mock_coro()
        mock_controller.sites.return_value = mock_coro({
            'site1': {'name': 'default', 'role': 'viewer', 'desc': 'site name'}
        })

        await flow.async_step_user(user_input={
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_PORT: 1234,
            unifi.CONF_VERIFY_SSL: True
        })

        result = await flow.async_step_site(user_input={})

    assert result['type'] == 'abort'


async def test_user_credentials_faulty(hass, aioclient_mock):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    with patch.object(unifi, 'get_controller',
                      side_effect=unifi.errors.AuthenticationRequired):
        result = await flow.async_step_user({
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_SITE_ID: 'default',
        })

    assert result['type'] == 'form'
    assert result['errors'] == {'base': 'faulty_credentials'}


async def test_controller_is_unavailable(hass, aioclient_mock):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    with patch.object(unifi, 'get_controller',
                      side_effect=unifi.errors.CannotConnect):
        result = await flow.async_step_user({
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_SITE_ID: 'default',
        })

    assert result['type'] == 'form'
    assert result['errors'] == {'base': 'service_unavailable'}


async def test_controller_unkown_problem(hass, aioclient_mock):
    """Test config flow."""
    flow = unifi.UnifiFlowHandler()
    flow.hass = hass

    with patch.object(unifi, 'get_controller',
                      side_effect=Exception):
        result = await flow.async_step_user({
            unifi.CONF_HOST: '1.2.3.4',
            unifi.CONF_USERNAME: 'username',
            unifi.CONF_PASSWORD: 'password',
            unifi.CONF_SITE_ID: 'default',
        })

    assert result['type'] == 'abort'

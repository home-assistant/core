"""Test Axis config flow."""
from unittest.mock import Mock, patch

from homeassistant.components import axis
from homeassistant.components.axis import config_flow

from tests.common import mock_coro, MockConfigEntry

import axis as axis_lib


async def test_configured_devices(hass):
    """Test that configured devices works as expected."""
    result = config_flow.configured_devices(hass)

    assert not result

    entry = MockConfigEntry(domain=axis.DOMAIN,
                            data={axis.CONF_DEVICE: {axis.CONF_HOST: ''}})
    entry.add_to_hass(hass)

    result = config_flow.configured_devices(hass)

    assert len(result) == 1


async def test_flow_works(hass):
    """Test that config flow works."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto, event_types,
                signal):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        def mock_get_param(param):
            """Fake get param method."""
            return param

        mock_device.side_effect = mock_constructor
        mock_device.vapix.load_params.return_value = Mock()
        mock_device.vapix.get_param.side_effect = mock_get_param

        result = await flow.async_step_user(user_input={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == '{} - {}'.format(
        axis_lib.vapix.VAPIX_MODEL_ID, axis_lib.vapix.VAPIX_SERIAL_NUMBER)
    assert result['data'] == {
        axis.CONF_DEVICE: {
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81
        },
        config_flow.CONF_MAC: axis_lib.vapix.VAPIX_SERIAL_NUMBER,
        config_flow.CONF_MODEL: axis_lib.vapix.VAPIX_MODEL_ID,
        config_flow.CONF_NAME: 'Brand.ProdNbr 0'
    }


async def test_flow_fails_already_configured(hass):
    """Test that config flow fails on already configured device."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    entry = MockConfigEntry(domain=axis.DOMAIN, data={axis.CONF_DEVICE: {
        axis.CONF_HOST: '1.2.3.4'
    }})
    entry.add_to_hass(hass)

    result = await flow.async_step_user(user_input={
        config_flow.CONF_HOST: '1.2.3.4',
        config_flow.CONF_USERNAME: 'user',
        config_flow.CONF_PASSWORD: 'pass',
        config_flow.CONF_PORT: 81
    })

    assert result['errors'] == {'base': 'already_configured'}


async def test_flow_fails_faulty_credentials(hass):
    """Test that config flow fails on faulty credentials."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('homeassistant.components.axis.config_flow.get_device',
               side_effect=config_flow.AuthenticationRequired):
        result = await flow.async_step_user(user_input={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81
        })

    assert result['errors'] == {'base': 'faulty_credentials'}


async def test_flow_fails_device_unavailable(hass):
    """Test that config flow fails on device unavailable."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('homeassistant.components.axis.config_flow.get_device',
               side_effect=config_flow.CannotConnect):
        result = await flow.async_step_user(user_input={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81
        })

    assert result['errors'] == {'base': 'device_unavailable'}


async def test_flow_create_entry(hass):
    """Test that create entry can generate a name without other entries."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass
    flow.model = 'model'

    result = await flow._create_entry()

    assert result['data'][config_flow.CONF_NAME] == 'model 0'


async def test_flow_create_entry_more_entries(hass):
    """Test that create entry can generate a name with other entries."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN, data={config_flow.CONF_NAME: 'model 0',
                                  config_flow.CONF_MODEL: 'model'})
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=axis.DOMAIN, data={config_flow.CONF_NAME: 'model 1',
                                  config_flow.CONF_MODEL: 'model'})
    entry2.add_to_hass(hass)

    flow = config_flow.AxisFlowHandler()
    flow.hass = hass
    flow.model = 'model'

    result = await flow._create_entry()

    assert result['data'][config_flow.CONF_NAME] == 'model 2'


async def test_discovery_flow(hass):
    """Test that discovery for new devices work."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch.object(axis, 'get_device', return_value=mock_coro(Mock())):
        result = await flow.async_step_discovery(discovery_info={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_PORT: 80,
            'properties': {'macaddress': '1234'}
        })

    assert result['type'] == 'form'
    assert result['step_id'] == 'user'


async def test_discovery_flow_known_device(hass):
    """Test that discovery for known devices work.

    This is legacy support from devices registered with configurator.
    """
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('homeassistant.components.axis.config_flow.load_json',
               return_value={'1234ABCD': {
                   config_flow.CONF_HOST: '2.3.4.5',
                   config_flow.CONF_USERNAME: 'user',
                   config_flow.CONF_PASSWORD: 'pass',
                   config_flow.CONF_PORT: 80}}), \
            patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto, event_types,
                signal):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        def mock_get_param(param):
            """Fake get param method."""
            return param

        mock_device.side_effect = mock_constructor
        mock_device.vapix.load_params.return_value = Mock()
        mock_device.vapix.get_param.side_effect = mock_get_param

        result = await flow.async_step_discovery(discovery_info={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_PORT: 80,
            'hostname': 'name',
            'properties': {'macaddress': '1234ABCD'}
        })

    assert result['type'] == 'create_entry'


async def test_discovery_flow_already_configured(hass):
    """Test that discovery doesn't setup already configured devices."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    entry = MockConfigEntry(domain=axis.DOMAIN, data={axis.CONF_DEVICE: {
        axis.CONF_HOST: '1.2.3.4'
    }})
    entry.add_to_hass(hass)

    result = await flow.async_step_discovery(discovery_info={
        config_flow.CONF_HOST: '1.2.3.4',
        config_flow.CONF_USERNAME: 'user',
        config_flow.CONF_PASSWORD: 'pass',
        config_flow.CONF_PORT: 81
    })
    print(result)
    assert result['type'] == 'abort'


async def test_discovery_flow_link_local_address(hass):
    """Test that discovery doesn't setup devices with link local addresses."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info={
        config_flow.CONF_HOST: '169.254.3.4'
    })

    assert result['type'] == 'abort'


async def test_discovery_flow_bad_config_file(hass):
    """Test that discovery with bad config files abort."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('homeassistant.components.axis.config_flow.load_json',
               return_value={'1234ABCD': {
                   config_flow.CONF_HOST: '2.3.4.5',
                   config_flow.CONF_USERNAME: 'user',
                   config_flow.CONF_PASSWORD: 'pass',
                   config_flow.CONF_PORT: 80}}), \
            patch('homeassistant.components.axis.config_flow.DEVICE_SCHEMA',
                  side_effect=config_flow.vol.Invalid('')):
        result = await flow.async_step_discovery(discovery_info={
            config_flow.CONF_HOST: '1.2.3.4',
            'properties': {'macaddress': '1234ABCD'}
        })

    assert result['type'] == 'abort'


async def test_import_flow_works(hass):
    """Test that import flow works."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    with patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto, event_types,
                signal):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        def mock_get_param(param):
            """Fake get param method."""
            return param

        mock_device.side_effect = mock_constructor
        mock_device.vapix.load_params.return_value = Mock()
        mock_device.vapix.get_param.side_effect = mock_get_param

        result = await flow.async_step_import(import_config={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81,
            config_flow.CONF_NAME: 'name'
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == '{} - {}'.format(
        axis_lib.vapix.VAPIX_MODEL_ID, axis_lib.vapix.VAPIX_SERIAL_NUMBER)
    assert result['data'] == {
        axis.CONF_DEVICE: {
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 81
        },
        config_flow.CONF_MAC: axis_lib.vapix.VAPIX_SERIAL_NUMBER,
        config_flow.CONF_MODEL: axis_lib.vapix.VAPIX_MODEL_ID,
        config_flow.CONF_NAME: 'name'
    }

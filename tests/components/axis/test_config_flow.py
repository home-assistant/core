"""Test Axis config flow."""
from unittest.mock import Mock, patch

from homeassistant.components import axis
from homeassistant.components.axis import config_flow

from tests.common import mock_coro, MockConfigEntry


async def test_configured_devices(hass):
    """Test that configured devices works as expected."""
    result = config_flow.configured_devices(hass)

    assert not result

    entry = MockConfigEntry(domain=axis.DOMAIN,
                            data={axis.config_flow.CONF_MAC: '1234'})
    entry.add_to_hass(hass)

    result = config_flow.configured_devices(hass)

    assert len(result) == 1


async def test_flow_works(hass):
    """Test that config flow works."""
    with patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        mock_device.side_effect = mock_constructor
        mock_device.vapix.params.system_serialnumber = 'serialnumber'
        mock_device.vapix.params.prodnbr = 'prodnbr'

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={'source': 'user'}
        )

        assert result['type'] == 'form'
        assert result['step_id'] == 'user'

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'],
            user_input={
                config_flow.CONF_HOST: '1.2.3.4',
                config_flow.CONF_USERNAME: 'user',
                config_flow.CONF_PASSWORD: 'pass',
                config_flow.CONF_PORT: 80
            }
        )

    assert result['type'] == 'create_entry'
    assert result['title'] == '{} - {}'.format('prodnbr', 'serialnumber')
    assert result['data'] == {
        axis.CONF_DEVICE: {
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 80
        },
        config_flow.CONF_MAC: 'serialnumber',
        config_flow.CONF_MODEL: 'prodnbr',
        config_flow.CONF_NAME: 'prodnbr 0'
    }


async def test_flow_fails_already_configured(hass):
    """Test that config flow fails on already configured device."""
    flow = config_flow.AxisFlowHandler()
    flow.hass = hass

    entry = MockConfigEntry(domain=axis.DOMAIN,
                            data={axis.config_flow.CONF_MAC: '1234'})
    entry.add_to_hass(hass)

    mock_device = Mock()
    mock_device.vapix.params.system_serialnumber = '1234'

    with patch('homeassistant.components.axis.config_flow.get_device',
               return_value=mock_coro(mock_device)):
        result = await flow.async_step_user(user_input={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 80
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
            config_flow.CONF_PORT: 80
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
            config_flow.CONF_PORT: 80
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
    with patch.object(axis, 'get_device', return_value=mock_coro(Mock())):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            data={
                config_flow.CONF_HOST: '1.2.3.4',
                config_flow.CONF_PORT: 80,
                'properties': {'macaddress': '1234'}
            },
            context={'source': 'discovery'}
        )

    assert result['type'] == 'form'
    assert result['step_id'] == 'user'


async def test_discovery_flow_known_device(hass):
    """Test that discovery for known devices work.

    This is legacy support from devices registered with configurator.
    """
    with patch('homeassistant.components.axis.config_flow.load_json',
               return_value={'1234ABCD': {
                   config_flow.CONF_HOST: '2.3.4.5',
                   config_flow.CONF_USERNAME: 'user',
                   config_flow.CONF_PASSWORD: 'pass',
                   config_flow.CONF_PORT: 80}}), \
            patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        mock_device.side_effect = mock_constructor

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            data={
                config_flow.CONF_HOST: '1.2.3.4',
                config_flow.CONF_PORT: 80,
                'hostname': 'name',
                'properties': {'macaddress': '1234ABCD'}
            },
            context={'source': 'discovery'}
        )

    assert result['type'] == 'create_entry'


async def test_discovery_flow_already_configured(hass):
    """Test that discovery doesn't setup already configured devices."""
    entry = MockConfigEntry(
        domain=axis.DOMAIN,
        data={axis.CONF_DEVICE: {axis.config_flow.CONF_HOST: '1.2.3.4'},
              axis.config_flow.CONF_MAC: '1234ABCD'}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 80,
            'hostname': 'name',
            'properties': {'macaddress': '1234ABCD'}
        },
        context={'source': 'discovery'}
    )

    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'


async def test_discovery_flow_ignore_link_local_address(hass):
    """Test that discovery doesn't setup devices with link local addresses."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={config_flow.CONF_HOST: '169.254.3.4'},
        context={'source': 'discovery'}
    )

    assert result['type'] == 'abort'
    assert result['reason'] == 'link_local_address'


async def test_discovery_flow_bad_config_file(hass):
    """Test that discovery with bad config files abort."""
    with patch('homeassistant.components.axis.config_flow.load_json',
               return_value={'1234ABCD': {
                   config_flow.CONF_HOST: '2.3.4.5',
                   config_flow.CONF_USERNAME: 'user',
                   config_flow.CONF_PASSWORD: 'pass',
                   config_flow.CONF_PORT: 80}}), \
            patch('homeassistant.components.axis.config_flow.DEVICE_SCHEMA',
                  side_effect=config_flow.vol.Invalid('')):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            data={
                config_flow.CONF_HOST: '1.2.3.4',
                'properties': {'macaddress': '1234ABCD'}
            },
            context={'source': 'discovery'}
        )

    assert result['type'] == 'abort'
    assert result['reason'] == 'bad_config_file'


async def test_import_flow_works(hass):
    """Test that import flow works."""
    with patch('axis.AxisDevice') as mock_device:
        def mock_constructor(
                loop, host, username, password, port, web_proto):
            """Fake the controller constructor."""
            mock_device.loop = loop
            mock_device.host = host
            mock_device.username = username
            mock_device.password = password
            mock_device.port = port
            return mock_device

        mock_device.side_effect = mock_constructor
        mock_device.vapix.params.system_serialnumber = 'serialnumber'
        mock_device.vapix.params.prodnbr = 'prodnbr'

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            data={
                config_flow.CONF_HOST: '1.2.3.4',
                config_flow.CONF_USERNAME: 'user',
                config_flow.CONF_PASSWORD: 'pass',
                config_flow.CONF_PORT: 80,
                config_flow.CONF_NAME: 'name'
            },
            context={'source': 'import'}
        )

    assert result['type'] == 'create_entry'
    assert result['title'] == '{} - {}'.format('prodnbr', 'serialnumber')
    assert result['data'] == {
        axis.CONF_DEVICE: {
            config_flow.CONF_HOST: '1.2.3.4',
            config_flow.CONF_USERNAME: 'user',
            config_flow.CONF_PASSWORD: 'pass',
            config_flow.CONF_PORT: 80
        },
        config_flow.CONF_MAC: 'serialnumber',
        config_flow.CONF_MODEL: 'prodnbr',
        config_flow.CONF_NAME: 'name'
    }

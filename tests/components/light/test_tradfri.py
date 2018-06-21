"""Tradfri lights platform tests."""

from copy import deepcopy
from unittest.mock import Mock, MagicMock, patch, PropertyMock

import pytest
from pytradfri.device import Device, LightControl, Light
from pytradfri import RequestError

from homeassistant.components import tradfri
from homeassistant.setup import async_setup_component


DEFAULT_TEST_FEATURES = {'can_set_dimmer': False,
                         'can_set_color': False,
                         'can_set_temp': False}
# [
#     {bulb features},
#     {turn_on arguments},
#     {expected result}
# ]
TURN_ON_TEST_CASES = [
    # Turn On
    [
        {},
        {},
        {'state': 'on'},
    ],
    # Brightness > 0
    [
        {'can_set_dimmer': True},
        {'brightness': 100},
        {
            'state': 'on',
            'brightness': 100
        }
    ],
    # Brightness == 0
    [
        {'can_set_dimmer': True},
        {'brightness': 0},
        {
            'brightness': 0
        }
    ],
    # Brightness < 0
    [
        {'can_set_dimmer': True},
        {'brightness': -1},
        {
            'brightness': 0
        }
    ],
    # Brightness > 254
    [
        {'can_set_dimmer': True},
        {'brightness': 1000},
        {
            'brightness': 254
        }
    ],
    # color_temp
    [
        {'can_set_temp': True},
        {'color_temp': 250},
        {'color_temp': 250},
    ],
    # color_temp < 250
    [
        {'can_set_temp': True},
        {'color_temp': 1},
        {'color_temp': 250},
    ],
    # color_temp > 454
    [
        {'can_set_temp': True},
        {'color_temp': 1000},
        {'color_temp': 454},
    ],
    # hs color
    [
        {'can_set_color': True},
        {'hs_color': [300, 100]},
        {
            'state': 'on',
            'hs_color': [300, 100]
        }
    ],
    # ct + brightness
    [
        {
            'can_set_dimmer': True,
            'can_set_temp': True
        },
        {
            'color_temp': 250,
            'brightness': 200
        },
        {
            'state': 'on',
            'color_temp': 250,
            'brightness': 200
        }
    ],
    # ct + brightness (no temp support)
    [
        {
            'can_set_dimmer': True,
            'can_set_temp': False,
            'can_set_color': True
        },
        {
            'color_temp': 250,
            'brightness': 200
        },
        {
            'state': 'on',
            'hs_color': [26.807, 34.869],
            'brightness': 200
        }
    ],
    # ct + brightness (no temp or color support)
    [
        {
            'can_set_dimmer': True,
            'can_set_temp': False,
            'can_set_color': False
        },
        {
            'color_temp': 250,
            'brightness': 200
        },
        {
            'state': 'on',
            'brightness': 200
        }
    ],
    # hs + brightness
    [
        {
            'can_set_dimmer': True,
            'can_set_color': True
        },
        {
            'hs_color': [300, 100],
            'brightness': 200
        },
        {
            'state': 'on',
            'hs_color': [300, 100],
            'brightness': 200
        }
    ]
]

# Result of transition is not tested, but data is passed to turn on service.
TRANSITION_CASES_FOR_TESTS = [None, 0, 1]


@pytest.fixture(autouse=True, scope='module')
def setup(request):
    """Set up patches for pytradfri methods."""
    p_1 = patch('pytradfri.device.LightControl.raw',
                new_callable=PropertyMock,
                return_value=[{'mock': 'mock'}])
    p_2 = patch('pytradfri.device.LightControl.lights')
    p_1.start()
    p_2.start()

    def teardown():
        """Remove patches for pytradfri methods."""
        p_1.stop()
        p_2.stop()

    request.addfinalizer(teardown)


@pytest.fixture
def mock_gateway():
    """Mock a Tradfri gateway."""
    def get_devices():
        """Return mock devices."""
        return gateway.mock_devices

    def get_groups():
        """Return mock groups."""
        return gateway.mock_groups

    gateway = Mock(
        get_devices=get_devices,
        get_groups=get_groups,
        mock_devices=[],
        mock_groups=[],
        mock_responses=[]
    )
    return gateway


@pytest.fixture
def mock_api(mock_gateway):
    """Mock api."""
    async def api(self, command):
        """Mock api function."""
        # Store the data for "real" command objects.
        if(hasattr(command, '_data') and not isinstance(command, Mock)):
            mock_gateway.mock_responses.append(command._data)
        return command
    return api


async def generate_psk(self, code):
    """Mock psk."""
    return "mock"


async def setup_gateway(hass, mock_gateway, mock_api,
                        generate_psk=generate_psk,
                        known_hosts=None):
    """Load the Tradfri platform with a mock gateway."""
    def request_config(_, callback, description, submit_caption, fields):
        """Mock request_config."""
        hass.async_add_job(callback, {'security_code': 'mock'})

    if known_hosts is None:
        known_hosts = {}

    with patch('pytradfri.api.aiocoap_api.APIFactory.generate_psk',
               generate_psk), \
            patch('pytradfri.api.aiocoap_api.APIFactory.request', mock_api), \
            patch('pytradfri.Gateway', return_value=mock_gateway), \
            patch.object(tradfri, 'load_json', return_value=known_hosts), \
            patch.object(tradfri, 'save_json'), \
            patch.object(hass.components.configurator, 'request_config',
                         request_config):

        await async_setup_component(hass, tradfri.DOMAIN,
                                    {
                                        tradfri.DOMAIN: {
                                            'host': 'mock-host',
                                            'allow_tradfri_groups': True
                                        }
                                    })
        await hass.async_block_till_done()


async def test_setup_gateway(hass, mock_gateway, mock_api):
    """Test that the gateway can be setup without errors."""
    await setup_gateway(hass, mock_gateway, mock_api)


async def test_setup_gateway_known_host(hass, mock_gateway, mock_api):
    """Test gateway setup with a known host."""
    await setup_gateway(hass, mock_gateway, mock_api,
                        known_hosts={
                            'mock-host': {
                                'identity': 'mock',
                                'key': 'mock-key'
                                }
                            })


async def test_incorrect_security_code(hass, mock_gateway, mock_api):
    """Test that an error is shown if the security code is incorrect."""
    async def psk_error(self, code):
        """Raise RequestError when called."""
        raise RequestError

    with patch.object(hass.components.configurator, 'async_notify_errors') \
            as notify_error:
        await setup_gateway(hass, mock_gateway, mock_api,
                            generate_psk=psk_error)
        assert len(notify_error.mock_calls) > 0


def mock_light(test_features={}, test_state={}, n=0):
    """Mock a tradfri light."""
    mock_light_data = Mock(
        **test_state
    )

    mock_light = Mock(
        id='mock-light-id-{}'.format(n),
        reachable=True,
        observe=Mock(),
        device_info=MagicMock()
    )
    mock_light.name = 'tradfri_light_{}'.format(n)

    # Set supported features for the light.
    features = {**DEFAULT_TEST_FEATURES, **test_features}
    lc = LightControl(mock_light)
    for k, v in features.items():
        setattr(lc, k, v)
    # Store the initial state.
    setattr(lc, 'lights', [mock_light_data])
    mock_light.light_control = lc
    return mock_light


async def test_light(hass, mock_gateway, mock_api):
    """Test that lights are correctly added."""
    features = {
        'can_set_dimmer': True,
        'can_set_color': True,
        'can_set_temp': True
    }

    state = {
        'state': True,
        'dimmer': 100,
        'color_temp': 250,
        'hsb_xy_color': (100, 100, 100, 100, 100)
    }

    mock_gateway.mock_devices.append(
        mock_light(test_features=features, test_state=state)
    )
    await setup_gateway(hass, mock_gateway, mock_api)

    lamp_1 = hass.states.get('light.tradfri_light_0')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 100
    assert lamp_1.attributes['hs_color'] == (0.549, 0.153)


async def test_light_observed(hass, mock_gateway, mock_api):
    """Test that lights are correctly observed."""
    light = mock_light()
    mock_gateway.mock_devices.append(light)
    await setup_gateway(hass, mock_gateway, mock_api)
    assert len(light.observe.mock_calls) > 0


async def test_light_available(hass, mock_gateway, mock_api):
    """Test light available property."""
    light = mock_light({'state': True}, n=1)
    light.reachable = True

    light2 = mock_light({'state': True}, n=2)
    light2.reachable = False

    mock_gateway.mock_devices.append(light)
    mock_gateway.mock_devices.append(light2)
    await setup_gateway(hass, mock_gateway, mock_api)

    assert (hass.states.get('light.tradfri_light_1')
            .state == 'on')

    assert (hass.states.get('light.tradfri_light_2')
            .state == 'unavailable')


# Combine TURN_ON_TEST_CASES and TRANSITION_CASES_FOR_TESTS
ALL_TURN_ON_TEST_CASES = [
    ["test_features", "test_data", "expected_result", "id"],
    []
]

idx = 1
for tc in TURN_ON_TEST_CASES:
    for trans in TRANSITION_CASES_FOR_TESTS:
        case = deepcopy(tc)
        if trans is not None:
            case[1]['transition'] = trans
        case.append(idx)
        idx = idx + 1
        ALL_TURN_ON_TEST_CASES[1].append(case)


@pytest.mark.parametrize(*ALL_TURN_ON_TEST_CASES)
async def test_turn_on(hass,
                       mock_gateway,
                       mock_api,
                       test_features,
                       test_data,
                       expected_result,
                       id):
    """Test turning on a light."""
    # Note pytradfri style, not hass. Values not really important.
    initial_state = {
        'state': False,
        'dimmer': 0,
        'color_temp': 250,
        'hsb_xy_color': (100, 100, 100, 100, 100)
    }

    # Setup the gateway with a mock light.
    light = mock_light(test_features=test_features,
                       test_state=initial_state,
                       n=id)
    mock_gateway.mock_devices.append(light)
    await setup_gateway(hass, mock_gateway, mock_api)

    # Use the turn_on service call to change the light state.
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.tradfri_light_{}'.format(id),
        **test_data
    }, blocking=True)
    await hass.async_block_till_done()

    # Check that the light is observed.
    mock_func = light.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert 'callback' in callkwargs
    # Callback function to refresh light state.
    cb = callkwargs['callback']

    responses = mock_gateway.mock_responses
    # State on command data.
    data = {'3311': [{'5850': 1}]}
    # Add data for all sent commands.
    for r in responses:
        data['3311'][0] = {**data['3311'][0], **r['3311'][0]}

    # Use the callback function to update the light state.
    dev = Device(data)
    light_data = Light(dev, 0)
    light.light_control.lights[0] = light_data
    cb(light)
    await hass.async_block_till_done()

    # Check that the state is correct.
    states = hass.states.get('light.tradfri_light_{}'.format(id))
    for k, v in expected_result.items():
        if k == 'state':
            assert states.state == v
        else:
            # Allow some rounding error in color conversions.
            assert states.attributes[k] == pytest.approx(v, abs=0.01)


async def test_turn_off(hass, mock_gateway, mock_api):
    """Test turning off a light."""
    state = {
        'state': True,
        'dimmer': 100,
    }

    light = mock_light(test_state=state)
    mock_gateway.mock_devices.append(light)
    await setup_gateway(hass, mock_gateway, mock_api)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.tradfri_light_0'}, blocking=True)
    await hass.async_block_till_done()

    # Check that the light is observed.
    mock_func = light.observe
    assert len(mock_func.mock_calls) > 0
    _, callkwargs = mock_func.call_args
    assert 'callback' in callkwargs
    # Callback function to refresh light state.
    cb = callkwargs['callback']

    responses = mock_gateway.mock_responses
    data = {'3311': [{}]}
    # Add data for all sent commands.
    for r in responses:
        data['3311'][0] = {**data['3311'][0], **r['3311'][0]}

    # Use the callback function to update the light state.
    dev = Device(data)
    light_data = Light(dev, 0)
    light.light_control.lights[0] = light_data
    cb(light)
    await hass.async_block_till_done()

    # Check that the state is correct.
    states = hass.states.get('light.tradfri_light_0')
    assert states.state == 'off'


def mock_group(test_state={}, n=0):
    """Mock a Tradfri group."""
    default_state = {
        'state': False,
        'dimmer': 0,
    }

    state = {**default_state, **test_state}

    mock_group = Mock(
        member_ids=[],
        observe=Mock(),
        **state
    )
    mock_group.name = 'tradfri_group_{}'.format(n)
    return mock_group


async def test_group(hass, mock_gateway, mock_api):
    """Test that groups are correctly added."""
    mock_gateway.mock_groups.append(mock_group())
    state = {'state': True, 'dimmer': 100}
    mock_gateway.mock_groups.append(mock_group(state, 1))
    await setup_gateway(hass, mock_gateway, mock_api)

    group = hass.states.get('light.tradfri_group_0')
    assert group is not None
    assert group.state == 'off'

    group = hass.states.get('light.tradfri_group_1')
    assert group is not None
    assert group.state == 'on'
    assert group.attributes['brightness'] == 100


async def test_group_turn_on(hass, mock_gateway, mock_api):
    """Test turning on a group."""
    group = mock_group()
    group2 = mock_group(n=1)
    group3 = mock_group(n=2)
    mock_gateway.mock_groups.append(group)
    mock_gateway.mock_groups.append(group2)
    mock_gateway.mock_groups.append(group3)
    await setup_gateway(hass, mock_gateway, mock_api)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.tradfri_group_0'}, blocking=True)
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.tradfri_group_1',
        'brightness': 100}, blocking=True)
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.tradfri_group_2',
        'brightness': 100,
        'transition': 1}, blocking=True)
    await hass.async_block_till_done()

    group.set_state.assert_called_with(1)
    group2.set_dimmer.assert_called_with(100)
    group3.set_dimmer.assert_called_with(100, transition_time=10)


async def test_group_turn_off(hass, mock_gateway, mock_api):
    """Test turning off a group."""
    group = mock_group({'state': True})
    mock_gateway.mock_groups.append(group)
    await setup_gateway(hass, mock_gateway, mock_api)

    # Use the turn_off service call to change the light state.
    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.tradfri_group_0'}, blocking=True)
    await hass.async_block_till_done()

    group.set_state.assert_called_with(0)

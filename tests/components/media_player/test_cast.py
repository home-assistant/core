"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import asyncio
from typing import Optional
from unittest.mock import patch, MagicMock, Mock
from uuid import UUID

import pytest

from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.media_player import cast


@pytest.fixture(autouse=True)
def cast_mock():
    """Mock pychromecast."""
    with patch.dict('sys.modules', {
        'pychromecast': MagicMock(),
    }):
        yield


# pylint: disable=invalid-name
FakeUUID = UUID('57355bce-9364-4aa6-ac1e-eb849dccf9e2')


def get_fake_chromecast(host='192.168.178.42', port=8009,
                        uuid: Optional[UUID] = FakeUUID):
    """Generate a Fake Chromecast object with the specified arguments."""
    return MagicMock(host=host, port=port, uuid=uuid)


@asyncio.coroutine
def async_setup_cast(hass, config=None, discovery_info=None):
    """Helper to setup the cast platform."""
    if config is None:
        config = {}
    add_devices = Mock()

    yield from cast.async_setup_platform(hass, config, add_devices,
                                         discovery_info=discovery_info)
    yield from hass.async_block_till_done()

    return add_devices


@asyncio.coroutine
def async_setup_cast_internal_discovery(hass, config=None,
                                        discovery_info=None,
                                        no_from_host_patch=False):
    """Setup the cast platform and the discovery."""
    listener = MagicMock(services={})

    with patch('pychromecast.start_discovery',
               return_value=(listener, None)) as start_discovery:
        add_devices = yield from async_setup_cast(hass, config, discovery_info)
        yield from hass.async_block_till_done()
        yield from hass.async_block_till_done()

        assert start_discovery.call_count == 1

        discovery_callback = start_discovery.call_args[0][0]

    def discover_chromecast(service_name, chromecast):
        """Discover a chromecast device."""
        listener.services[service_name] = (
            chromecast.host, chromecast.port, chromecast.uuid, None, None)
        if no_from_host_patch:
            discovery_callback(service_name)
        else:
            with patch('pychromecast._get_chromecast_from_host',
                       return_value=chromecast):
                discovery_callback(service_name)

    return discover_chromecast, add_devices


@asyncio.coroutine
def test_start_discovery_called_once(hass):
    """Test pychromecast.start_discovery called exactly once."""
    with patch('pychromecast.start_discovery',
               return_value=(None, None)) as start_discovery:
        yield from async_setup_cast(hass)

        assert start_discovery.call_count == 1

        yield from async_setup_cast(hass)
        assert start_discovery.call_count == 1


@asyncio.coroutine
def test_stop_discovery_called_on_stop(hass):
    """Test pychromecast.stop_discovery called on shutdown."""
    with patch('pychromecast.start_discovery',
               return_value=(None, 'the-browser')) as start_discovery:
        yield from async_setup_cast(hass)

        assert start_discovery.call_count == 1

    with patch('pychromecast.stop_discovery') as stop_discovery:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        yield from hass.async_block_till_done()

        stop_discovery.assert_called_once_with('the-browser')

    with patch('pychromecast.start_discovery',
               return_value=(None, 'the-browser')) as start_discovery:
        yield from async_setup_cast(hass)

        assert start_discovery.call_count == 1


@asyncio.coroutine
def test_internal_discovery_callback_only_generates_once(hass):
    """Test _get_chromecast_from_host only called once per device."""
    discover_cast, _ = yield from async_setup_cast_internal_discovery(
        hass, no_from_host_patch=True)
    chromecast = get_fake_chromecast()

    with patch('pychromecast._get_chromecast_from_host',
               return_value=chromecast) as gen_chromecast:
        discover_cast('the-service', chromecast)
        mdns = (chromecast.host, chromecast.port, chromecast.uuid, None, None)
        gen_chromecast.assert_called_once_with(mdns, blocking=True, tries=10)

        discover_cast('the-service', chromecast)
        gen_chromecast.reset_mock()
        assert gen_chromecast.call_count == 0


@asyncio.coroutine
def test_internal_discovery_callback_calls_dispatcher(hass):
    """Test internal discovery calls dispatcher."""
    discover_cast, _ = yield from async_setup_cast_internal_discovery(hass)
    chromecast = get_fake_chromecast()

    with patch('pychromecast._get_chromecast_from_host',
               return_value=chromecast):
        signal = MagicMock()

        async_dispatcher_connect(hass, 'cast_discovered', signal)
        discover_cast('the-service', chromecast)
        yield from hass.async_block_till_done()

        signal.assert_called_once_with(chromecast)


@asyncio.coroutine
def test_internal_discovery_callback_with_connection_error(hass):
    """Test internal discovery not calling dispatcher on ConnectionError."""
    import pychromecast  # imports mock pychromecast

    pychromecast.ChromecastConnectionError = IOError

    discover_cast, _ = yield from async_setup_cast_internal_discovery(
        hass, no_from_host_patch=True)
    chromecast = get_fake_chromecast()

    with patch('pychromecast._get_chromecast_from_host',
               side_effect=pychromecast.ChromecastConnectionError):
        signal = MagicMock()

        async_dispatcher_connect(hass, 'cast_discovered', signal)
        discover_cast('the-service', chromecast)
        yield from hass.async_block_till_done()

        assert signal.call_count == 0


def test_create_cast_device_without_uuid(hass):
    """Test create a cast device without a UUID."""
    chromecast = get_fake_chromecast(uuid=None)
    cast_device = cast._async_create_cast_device(hass, chromecast)
    assert cast_device is not None


def test_create_cast_device_with_uuid(hass):
    """Test create cast devices with UUID."""
    added_casts = hass.data[cast.ADDED_CAST_DEVICES_KEY] = {}
    chromecast = get_fake_chromecast()
    cast_device = cast._async_create_cast_device(hass, chromecast)
    assert cast_device is not None
    assert chromecast.uuid in added_casts

    with patch.object(cast_device, 'async_set_chromecast') as mock_set:
        assert cast._async_create_cast_device(hass, chromecast) is None
        assert mock_set.call_count == 0

        chromecast = get_fake_chromecast(host='192.168.178.1')
        assert cast._async_create_cast_device(hass, chromecast) is None
        assert mock_set.call_count == 1
        mock_set.assert_called_once_with(chromecast)


@asyncio.coroutine
def test_normal_chromecast_not_starting_discovery(hass):
    """Test cast platform not starting discovery when not required."""
    import pychromecast  # imports mock pychromecast

    pychromecast.ChromecastConnectionError = IOError

    chromecast = get_fake_chromecast()

    with patch('pychromecast.Chromecast', return_value=chromecast):
        add_devices = yield from async_setup_cast(hass, {'host': 'host1'})
        assert add_devices.call_count == 1

        # Same entity twice
        add_devices = yield from async_setup_cast(hass, {'host': 'host1'})
        assert add_devices.call_count == 0

        hass.data[cast.ADDED_CAST_DEVICES_KEY] = {}
        add_devices = yield from async_setup_cast(
            hass, discovery_info={'host': 'host1', 'port': 8009})
        assert add_devices.call_count == 1

        hass.data[cast.ADDED_CAST_DEVICES_KEY] = {}
        add_devices = yield from async_setup_cast(
            hass, discovery_info={'host': 'host1', 'port': 42})
        assert add_devices.call_count == 0

    with patch('pychromecast.Chromecast',
               side_effect=pychromecast.ChromecastConnectionError):
        with pytest.raises(PlatformNotReady):
            yield from async_setup_cast(hass, {'host': 'host3'})


@asyncio.coroutine
def test_replay_past_chromecasts(hass):
    """Test cast platform re-playing past chromecasts when adding new one."""
    cast_group1 = get_fake_chromecast(host='host1', port=42)
    cast_group2 = get_fake_chromecast(host='host2', port=42, uuid=UUID(
        '9462202c-e747-4af5-a66b-7dce0e1ebc09'))

    discover_cast, add_dev1 = yield from async_setup_cast_internal_discovery(
        hass, discovery_info={'host': 'host1', 'port': 42})
    discover_cast('service2', cast_group2)
    yield from hass.async_block_till_done()
    assert add_dev1.call_count == 0

    discover_cast('service1', cast_group1)
    yield from hass.async_block_till_done()
    yield from hass.async_block_till_done()  # having jobs that add jobs
    assert add_dev1.call_count == 1

    add_dev2 = yield from async_setup_cast(
        hass, discovery_info={'host': 'host2', 'port': 42})
    yield from hass.async_block_till_done()
    assert add_dev2.call_count == 1

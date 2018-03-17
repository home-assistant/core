"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import asyncio
from typing import Optional
from unittest.mock import patch, MagicMock, Mock
from uuid import UUID

import attr
import pytest

from homeassistant.components.media_player.cast import ChromecastInfo
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


def get_fake_chromecast(info: ChromecastInfo):
    """Generate a Fake Chromecast object with the specified arguments."""
    return MagicMock(host=info.host, port=info.port, uuid=info.uuid)


def get_fake_chromecast_info(host='192.168.178.42', port=8009,
                             uuid: Optional[UUID] = FakeUUID):
    """Generate a Fake ChromecastInfo with the specified arguments."""
    return ChromecastInfo(host=host, port=port, uuid=uuid)


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
                                        discovery_info=None):
    """Setup the cast platform and the discovery."""
    listener = MagicMock(services={})

    with patch('pychromecast.start_discovery',
               return_value=(listener, None)) as start_discovery:
        add_devices = yield from async_setup_cast(hass, config, discovery_info)
        yield from hass.async_block_till_done()
        yield from hass.async_block_till_done()

        assert start_discovery.call_count == 1

        discovery_callback = start_discovery.call_args[0][0]

    def discover_chromecast(service_name: str, info: ChromecastInfo) -> None:
        """Discover a chromecast device."""
        listener.services[service_name] = (info.host, info.port,
                                           info.uuid, info.model_name, None)
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


async def test_internal_discovery_callback_only_generates_once(hass):
    """Test discovery only called once per device."""
    discover_cast, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info()

    signal = MagicMock()
    async_dispatcher_connect(hass, 'cast_discovered', signal)

    with patch('pychromecast.dial.get_device_status', return_value=None):
        discover_cast('the-service', info)
        await hass.async_block_till_done()
        discover = signal.mock_calls[0][1][0]
        # attr's __eq__ somehow breaks here, use tuples instead
        assert attr.astuple(discover) == attr.astuple(info)
        signal.reset_mock()

        discover_cast('the-service', info)
        await hass.async_block_till_done()
        assert signal.call_count == 0


async def test_internal_discovery_callback_fill_out(hass):
    """Test internal discovery automatically filling out information."""
    import pychromecast  # imports mock pychromecast

    pychromecast.ChromecastConnectionError = IOError

    discover_cast, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info(uuid=None)
    full_info = attr.evolve(info, model_name='google home',
                            friendly_name='Speaker', uuid=FakeUUID)

    with patch('pychromecast.dial.get_device_status',
               return_value=full_info):
        signal = MagicMock()

        async_dispatcher_connect(hass, 'cast_discovered', signal)
        discover_cast('the-service', info)
        await hass.async_block_till_done()

        discover = signal.mock_calls[0][1][0]
        # attr's __eq__ somehow breaks here, use tuples instead
        assert attr.astuple(discover) == attr.astuple(full_info)


def test_create_cast_device_without_uuid(hass):
    """Test create a cast device without a UUID."""
    info = get_fake_chromecast_info(uuid=None)
    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is not None


def test_create_cast_device_with_uuid(hass):
    """Test create cast devices with UUID."""
    added_casts = hass.data[cast.ADDED_CAST_DEVICES_KEY] = set()
    info = get_fake_chromecast_info()

    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is not None
    assert info.uuid in added_casts

    # Sending second time should not create new entity
    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is None


@patch('homeassistant.components.media_player.cast._setup_internal_discovery')
async def test_normal_chromecast_not_starting_discovery(hass):
    """Test cast platform not starting discovery when not required."""
    # pylint: disable=no-member
    add_devices = await async_setup_cast(hass, {'host': 'host1'})
    await hass.async_block_till_done()
    assert add_devices.call_count == 1
    assert cast._setup_internal_discovery.call_count == 0

    # Same entity twice
    add_devices = await async_setup_cast(hass, {'host': 'host1'})
    await hass.async_block_till_done()
    assert add_devices.call_count == 0
    assert cast._setup_internal_discovery.call_count == 0

    hass.data[cast.ADDED_CAST_DEVICES_KEY] = {}
    add_devices = await async_setup_cast(
        hass, discovery_info={'host': 'host1', 'port': 8009})
    await hass.async_block_till_done()
    assert add_devices.call_count == 1
    assert cast._setup_internal_discovery.call_count == 0

    hass.data[cast.ADDED_CAST_DEVICES_KEY] = {}
    add_devices = await async_setup_cast(
        hass, discovery_info={'host': 'host1', 'port': 42})
    await hass.async_block_till_done()
    assert add_devices.call_count == 0
    assert cast._setup_internal_discovery.call_count == 1


async def test_replay_past_chromecasts(hass):
    """Test cast platform re-playing past chromecasts when adding new one."""
    cast_group1 = get_fake_chromecast_info(host='host1', port=42)
    cast_group2 = get_fake_chromecast_info(host='host2', port=42, uuid=UUID(
        '9462202c-e747-4af5-a66b-7dce0e1ebc09'))

    discover_cast, add_dev1 = await async_setup_cast_internal_discovery(
        hass, discovery_info={'host': 'host1', 'port': 42})
    discover_cast('service2', cast_group2)
    await hass.async_block_till_done()
    assert add_dev1.call_count == 0

    discover_cast('service1', cast_group1)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    add_dev2 = await async_setup_cast(
        hass, discovery_info={'host': 'host2', 'port': 42})
    await hass.async_block_till_done()
    assert add_dev2.call_count == 1

"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import asyncio
from typing import Optional
from unittest.mock import patch, MagicMock, Mock
from uuid import UUID

import attr
import pytest

from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.media_player.cast import ChromecastInfo
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect, \
    async_dispatcher_send
from homeassistant.components.media_player import cast
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


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
    mock = MagicMock(host=info.host, port=info.port, uuid=info.uuid)
    mock.media_controller.status = None
    return mock


def get_fake_chromecast_info(host='192.168.178.42', port=8009,
                             uuid: Optional[UUID] = FakeUUID):
    """Generate a Fake ChromecastInfo with the specified arguments."""
    return ChromecastInfo(host=host, port=port, uuid=uuid,
                          friendly_name="Speaker")


async def async_setup_cast(hass, config=None, discovery_info=None):
    """Helper to setup the cast platform."""
    if config is None:
        config = {}
    add_devices = Mock()

    await cast.async_setup_platform(hass, config, add_devices,
                                    discovery_info=discovery_info)
    await hass.async_block_till_done()

    return add_devices


async def async_setup_cast_internal_discovery(hass, config=None,
                                              discovery_info=None):
    """Setup the cast platform and the discovery."""
    listener = MagicMock(services={})

    with patch('pychromecast.start_discovery',
               return_value=(listener, None)) as start_discovery:
        add_devices = await async_setup_cast(hass, config, discovery_info)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert start_discovery.call_count == 1

        discovery_callback = start_discovery.call_args[0][0]

    def discover_chromecast(service_name: str, info: ChromecastInfo) -> None:
        """Discover a chromecast device."""
        listener.services[service_name] = attr.astuple(info)
        discovery_callback(service_name)

    return discover_chromecast, add_devices


async def async_setup_media_player_cast(hass: HomeAssistantType,
                                        info: ChromecastInfo):
    """Setup the cast platform with async_setup_component."""
    chromecast = get_fake_chromecast(info)

    cast.CastStatusListener = MagicMock()

    with patch('pychromecast._get_chromecast_from_host',
               return_value=chromecast) as get_chromecast:
        await async_setup_component(hass, 'media_player', {
            'media_player': {'platform': 'cast', 'host': info.host}})
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 1
        assert cast.CastStatusListener.call_count == 1
        entity = cast.CastStatusListener.call_args[0][0]
        return chromecast, entity


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
        # start_discovery should be called with empty config
        yield from async_setup_cast(hass, {})

        assert start_discovery.call_count == 1

    with patch('pychromecast.stop_discovery') as stop_discovery:
        # stop discovery should be called on shutdown
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        yield from hass.async_block_till_done()

        stop_discovery.assert_called_once_with('the-browser')

    with patch('pychromecast.start_discovery',
               return_value=(None, 'the-browser')) as start_discovery:
        # start_discovery should be called again on re-startup
        yield from async_setup_cast(hass)

        assert start_discovery.call_count == 1


async def test_internal_discovery_callback_only_generates_once(hass):
    """Test discovery only called once per device."""
    discover_cast, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info()

    signal = MagicMock()
    async_dispatcher_connect(hass, 'cast_discovered', signal)

    with patch('pychromecast.dial.get_device_status', return_value=None):
        # discovering a cast device should call the dispatcher
        discover_cast('the-service', info)
        await hass.async_block_till_done()
        discover = signal.mock_calls[0][1][0]
        # attr's __eq__ somehow breaks here, use tuples instead
        assert attr.astuple(discover) == attr.astuple(info)
        signal.reset_mock()

        # discovering it a second time shouldn't
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

        # when called with incomplete info, it should use HTTP to get missing
        discover = signal.mock_calls[0][1][0]
        # attr's __eq__ somehow breaks here, use tuples instead
        assert attr.astuple(discover) == attr.astuple(full_info)


async def test_create_cast_device_without_uuid(hass):
    """Test create a cast device with no UUId should still create an entity."""
    info = get_fake_chromecast_info(uuid=None)
    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is not None


async def test_create_cast_device_with_uuid(hass):
    """Test create cast devices with UUID creates entities."""
    added_casts = hass.data[cast.ADDED_CAST_DEVICES_KEY] = set()
    info = get_fake_chromecast_info()

    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is not None
    assert info.uuid in added_casts

    # Sending second time should not create new entity
    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is None


async def test_normal_chromecast_not_starting_discovery(hass):
    """Test cast platform not starting discovery when not required."""
    # pylint: disable=no-member
    with patch('homeassistant.components.media_player.cast.'
               '_setup_internal_discovery') as setup_discovery:
        # normal (non-group) chromecast shouldn't start discovery.
        add_devices = await async_setup_cast(hass, {'host': 'host1'})
        await hass.async_block_till_done()
        assert add_devices.call_count == 1
        assert setup_discovery.call_count == 0

        # Same entity twice
        add_devices = await async_setup_cast(hass, {'host': 'host1'})
        await hass.async_block_till_done()
        assert add_devices.call_count == 0
        assert setup_discovery.call_count == 0

        hass.data[cast.ADDED_CAST_DEVICES_KEY] = set()
        add_devices = await async_setup_cast(
            hass, discovery_info={'host': 'host1', 'port': 8009})
        await hass.async_block_till_done()
        assert add_devices.call_count == 1
        assert setup_discovery.call_count == 0

        # group should start discovery.
        hass.data[cast.ADDED_CAST_DEVICES_KEY] = set()
        add_devices = await async_setup_cast(
            hass, discovery_info={'host': 'host1', 'port': 42})
        await hass.async_block_till_done()
        assert add_devices.call_count == 0
        assert setup_discovery.call_count == 1


async def test_normal_raises_platform_not_ready(hass):
    """Test cast platform raises PlatformNotReady if HTTP dial fails."""
    with patch('pychromecast.dial.get_device_status', return_value=None):
        with pytest.raises(PlatformNotReady):
            await async_setup_cast(hass, {'host': 'host1'})


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


async def test_entity_media_states(hass: HomeAssistantType):
    """Test various entity media states."""
    info = get_fake_chromecast_info()
    full_info = attr.evolve(info, model_name='google home',
                            friendly_name='Speaker', uuid=FakeUUID)

    with patch('pychromecast.dial.get_device_status',
               return_value=full_info):
        chromecast, entity = await async_setup_media_player_cast(hass, info)

    state = hass.states.get('media_player.speaker')
    assert state is not None
    assert state.name == 'Speaker'
    assert state.state == 'unknown'
    assert entity.unique_id == full_info.uuid

    media_status = MagicMock(images=None)
    media_status.player_is_playing = True
    entity.new_media_status(media_status)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.speaker')
    assert state.state == 'playing'

    entity.new_media_status(media_status)
    media_status.player_is_playing = False
    media_status.player_is_paused = True
    await hass.async_block_till_done()
    state = hass.states.get('media_player.speaker')
    assert state.state == 'paused'

    entity.new_media_status(media_status)
    media_status.player_is_paused = False
    media_status.player_is_idle = True
    await hass.async_block_till_done()
    state = hass.states.get('media_player.speaker')
    assert state.state == 'idle'

    media_status.player_is_idle = False
    chromecast.is_idle = True
    entity.new_media_status(media_status)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.speaker')
    assert state.state == 'off'

    chromecast.is_idle = False
    entity.new_media_status(media_status)
    await hass.async_block_till_done()
    state = hass.states.get('media_player.speaker')
    assert state.state == 'unknown'


async def test_switched_host(hass: HomeAssistantType):
    """Test cast device listens for changed hosts and disconnects old cast."""
    info = get_fake_chromecast_info()
    full_info = attr.evolve(info, model_name='google home',
                            friendly_name='Speaker', uuid=FakeUUID)

    with patch('pychromecast.dial.get_device_status',
               return_value=full_info):
        chromecast, _ = await async_setup_media_player_cast(hass, full_info)

    chromecast2 = get_fake_chromecast(info)
    with patch('pychromecast._get_chromecast_from_host',
               return_value=chromecast2) as get_chromecast:
        async_dispatcher_send(hass, cast.SIGNAL_CAST_DISCOVERED, full_info)
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 0

        changed = attr.evolve(full_info, friendly_name='Speaker 2')
        async_dispatcher_send(hass, cast.SIGNAL_CAST_DISCOVERED, changed)
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 0

        changed = attr.evolve(changed, host='host2')
        async_dispatcher_send(hass, cast.SIGNAL_CAST_DISCOVERED, changed)
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 1
        assert chromecast.disconnect.call_count == 1


async def test_disconnect_on_stop(hass: HomeAssistantType):
    """Test cast device disconnects socket on stop."""
    info = get_fake_chromecast_info()

    with patch('pychromecast.dial.get_device_status', return_value=info):
        chromecast, _ = await async_setup_media_player_cast(hass, info)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert chromecast.disconnect.call_count == 1


async def test_entry_setup_no_config(hass: HomeAssistantType):
    """Test setting up entry with no config.."""
    await async_setup_component(hass, 'cast', {})

    with patch(
        'homeassistant.components.media_player.cast._async_setup_platform',
            return_value=mock_coro()) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == {}


async def test_entry_setup_single_config(hass: HomeAssistantType):
    """Test setting up entry and having a single config option."""
    await async_setup_component(hass, 'cast', {
        'cast': {
            'media_player': {
                'host': 'bla'
            }
        }
    })

    with patch(
        'homeassistant.components.media_player.cast._async_setup_platform',
            return_value=mock_coro()) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == {'host': 'bla'}


async def test_entry_setup_list_config(hass: HomeAssistantType):
    """Test setting up entry and having multiple config options."""
    await async_setup_component(hass, 'cast', {
        'cast': {
            'media_player': [
                {'host': 'bla'},
                {'host': 'blu'},
            ]
        }
    })

    with patch(
        'homeassistant.components.media_player.cast._async_setup_platform',
            return_value=mock_coro()) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 2
    assert mock_setup.mock_calls[0][1][1] == {'host': 'bla'}
    assert mock_setup.mock_calls[1][1][1] == {'host': 'blu'}

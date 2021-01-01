"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import json
from typing import Optional
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import attr
import pytest

from homeassistant.components import tts
from homeassistant.components.cast import media_player as cast
from homeassistant.components.cast.media_player import ChromecastInfo
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component
from tests.components.media_player import common


@pytest.fixture()
def mz_mock():
    """Mock pychromecast MultizoneManager."""
    return MagicMock()


@pytest.fixture()
def quick_play_mock():
    """Mock pychromecast quick_play."""
    return MagicMock()


@pytest.fixture(autouse=True)
def cast_mock(mz_mock, quick_play_mock):
    """Mock pychromecast."""
    pycast_mock = MagicMock()
    pycast_mock.start_discovery.return_value = (None, Mock())
    dial_mock = MagicMock(name="XXX")
    dial_mock.get_device_status.return_value.uuid = "fake_uuid"
    dial_mock.get_device_status.return_value.manufacturer = "fake_manufacturer"
    dial_mock.get_device_status.return_value.model_name = "fake_model_name"
    dial_mock.get_device_status.return_value.friendly_name = "fake_friendly_name"

    with patch(
        "homeassistant.components.cast.media_player.pychromecast", pycast_mock
    ), patch(
        "homeassistant.components.cast.discovery.pychromecast", pycast_mock
    ), patch(
        "homeassistant.components.cast.media_player.MultizoneManager",
        return_value=mz_mock,
    ), patch(
        "homeassistant.components.cast.media_player.zeroconf.async_get_instance",
        AsyncMock(),
    ), patch(
        "homeassistant.components.cast.media_player.quick_play",
        quick_play_mock,
    ):
        yield


# pylint: disable=invalid-name
FakeUUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e2")
FakeUUID2 = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e4")
FakeGroupUUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e3")


def get_fake_chromecast(info: ChromecastInfo):
    """Generate a Fake Chromecast object with the specified arguments."""
    mock = MagicMock(host=info.host, port=info.port, uuid=info.uuid)
    mock.media_controller.status = None
    return mock


def get_fake_chromecast_info(
    host="192.168.178.42", port=8009, uuid: Optional[UUID] = FakeUUID
):
    """Generate a Fake ChromecastInfo with the specified arguments."""
    return ChromecastInfo(
        host=host,
        port=port,
        uuid=uuid,
        friendly_name="Speaker",
        services={"the-service"},
    )


def get_fake_zconf(host="192.168.178.42", port=8009):
    """Generate a Fake Zeroconf object with the specified arguments."""
    parsed_addresses = MagicMock()
    parsed_addresses.return_value = [host]
    service_info = MagicMock(parsed_addresses=parsed_addresses, port=port)
    zconf = MagicMock()
    zconf.get_service_info.return_value = service_info
    return zconf


async def async_setup_cast(hass, config=None):
    """Set up the cast platform."""
    if config is None:
        config = {}
    with patch(
        "homeassistant.helpers.entity_platform.EntityPlatform._async_schedule_add_entities"
    ) as add_entities:
        MockConfigEntry(domain="cast").add_to_hass(hass)
        await async_setup_component(hass, "cast", {"cast": {"media_player": config}})
        await hass.async_block_till_done()

    return add_entities


async def async_setup_cast_internal_discovery(hass, config=None):
    """Set up the cast platform and the discovery."""
    listener = MagicMock(services={})
    browser = MagicMock(zc={})

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.CastListener",
        return_value=listener,
    ) as cast_listener, patch(
        "homeassistant.components.cast.discovery.pychromecast.start_discovery",
        return_value=browser,
    ) as start_discovery:
        add_entities = await async_setup_cast(hass, config)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert start_discovery.call_count == 1

        discovery_callback = cast_listener.call_args[0][0]

    def discover_chromecast(service_name: str, info: ChromecastInfo) -> None:
        """Discover a chromecast device."""
        listener.services[info.uuid] = (
            {service_name},
            info.uuid,
            info.model_name,
            info.friendly_name,
        )
        discovery_callback(info.uuid, service_name)

    return discover_chromecast, add_entities


async def async_setup_media_player_cast(hass: HomeAssistantType, info: ChromecastInfo):
    """Set up the cast platform with async_setup_component."""
    listener = MagicMock(services={})
    browser = MagicMock(zc={})
    chromecast = get_fake_chromecast(info)
    zconf = get_fake_zconf(host=info.host, port=info.port)

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.get_chromecast_from_service",
        return_value=chromecast,
    ) as get_chromecast, patch(
        "homeassistant.components.cast.discovery.pychromecast.CastListener",
        return_value=listener,
    ) as cast_listener, patch(
        "homeassistant.components.cast.discovery.pychromecast.start_discovery",
        return_value=browser,
    ), patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf,
    ):
        await async_setup_component(
            hass, "cast", {"cast": {"media_player": {"uuid": info.uuid}}}
        )
        await hass.async_block_till_done()

        discovery_callback = cast_listener.call_args[0][0]

        service_name = "the-service"
        listener.services[info.uuid] = (
            {service_name},
            info.uuid,
            info.model_name,
            info.friendly_name,
        )
        discovery_callback(info.uuid, service_name)

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 1
        return chromecast


def get_status_callbacks(chromecast_mock, mz_mock=None):
    """Get registered status callbacks from the chromecast mock."""
    status_listener = chromecast_mock.register_status_listener.call_args[0][0]
    cast_status_cb = status_listener.new_cast_status

    connection_listener = chromecast_mock.register_connection_listener.call_args[0][0]
    conn_status_cb = connection_listener.new_connection_status

    mc = chromecast_mock.socket_client.media_controller
    media_status_cb = mc.register_status_listener.call_args[0][0].new_media_status

    if not mz_mock:
        return cast_status_cb, conn_status_cb, media_status_cb

    mz_listener = mz_mock.register_listener.call_args[0][1]
    group_media_status_cb = mz_listener.multizone_new_media_status
    return cast_status_cb, conn_status_cb, media_status_cb, group_media_status_cb


async def test_start_discovery_called_once(hass):
    """Test pychromecast.start_discovery called exactly once."""
    with patch(
        "homeassistant.components.cast.discovery.pychromecast.start_discovery",
        return_value=Mock(),
    ) as start_discovery:
        await async_setup_cast(hass)

        assert start_discovery.call_count == 1

        await async_setup_cast(hass)
        assert start_discovery.call_count == 1


async def test_stop_discovery_called_on_stop(hass):
    """Test pychromecast.stop_discovery called on shutdown."""
    browser = MagicMock(zc={})

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.start_discovery",
        return_value=browser,
    ) as start_discovery:
        # start_discovery should be called with empty config
        await async_setup_cast(hass, {})

        assert start_discovery.call_count == 1

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.discovery.stop_discovery"
    ) as stop_discovery:
        # stop discovery should be called on shutdown
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        stop_discovery.assert_called_once_with(browser)


async def test_create_cast_device_without_uuid(hass):
    """Test create a cast device with no UUId does not create an entity."""
    info = get_fake_chromecast_info(uuid=None)
    cast_device = cast._async_create_cast_device(hass, info)
    assert cast_device is None


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


async def test_replay_past_chromecasts(hass):
    """Test cast platform re-playing past chromecasts when adding new one."""
    cast_group1 = get_fake_chromecast_info(host="host1", port=8009, uuid=FakeUUID)
    cast_group2 = get_fake_chromecast_info(
        host="host2", port=8009, uuid=UUID("9462202c-e747-4af5-a66b-7dce0e1ebc09")
    )
    zconf_1 = get_fake_zconf(host="host1", port=8009)
    zconf_2 = get_fake_zconf(host="host2", port=8009)

    discover_cast, add_dev1 = await async_setup_cast_internal_discovery(
        hass, config={"uuid": FakeUUID}
    )

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast("service2", cast_group2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 0

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast("service1", cast_group1)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    add_dev2 = Mock()
    await cast._async_setup_platform(hass, {"host": "host2"}, add_dev2)
    await hass.async_block_till_done()
    assert add_dev2.call_count == 1


async def test_manual_cast_chromecasts_uuid(hass):
    """Test only wanted casts are added for manual configuration."""
    cast_1 = get_fake_chromecast_info(host="host_1", uuid=FakeUUID)
    cast_2 = get_fake_chromecast_info(host="host_2", uuid=FakeUUID2)
    zconf_1 = get_fake_zconf(host="host_1")
    zconf_2 = get_fake_zconf(host="host_2")

    # Manual configuration of media player with host "configured_host"
    discover_cast, add_dev1 = await async_setup_cast_internal_discovery(
        hass, config={"uuid": FakeUUID}
    )
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast("service2", cast_2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 0

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast("service1", cast_1)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1


async def test_auto_cast_chromecasts(hass):
    """Test all discovered casts are added for default configuration."""
    cast_1 = get_fake_chromecast_info(host="some_host")
    cast_2 = get_fake_chromecast_info(host="other_host", uuid=FakeUUID2)
    zconf_1 = get_fake_zconf(host="some_host")
    zconf_2 = get_fake_zconf(host="other_host")

    # Manual configuration of media player with host "configured_host"
    discover_cast, add_dev1 = await async_setup_cast_internal_discovery(hass)
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast("service2", cast_2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast("service1", cast_1)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 2


async def test_update_cast_chromecasts(hass):
    """Test discovery of same UUID twice only adds one cast."""
    cast_1 = get_fake_chromecast_info(host="old_host")
    cast_2 = get_fake_chromecast_info(host="new_host")
    zconf_1 = get_fake_zconf(host="old_host")
    zconf_2 = get_fake_zconf(host="new_host")

    # Manual configuration of media player with host "configured_host"
    discover_cast, add_dev1 = await async_setup_cast_internal_discovery(hass)

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast("service1", cast_1)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast("service2", cast_2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1


async def test_entity_availability(hass: HomeAssistantType):
    """Test handling of connection status."""
    entity_id = "media_player.speaker"
    info = get_fake_chromecast_info()

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unknown"

    connection_status = MagicMock()
    connection_status.status = "DISCONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unavailable"


async def test_entity_cast_status(hass: HomeAssistantType):
    """Test handling of cast status."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    cast_status_cb, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    cast_status = MagicMock()
    cast_status.volume_level = 0.5
    cast_status.volume_muted = False
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("volume_level") == 0.5
    assert not state.attributes.get("is_volume_muted")

    cast_status = MagicMock()
    cast_status.volume_level = 0.2
    cast_status.volume_muted = True
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("volume_level") == 0.2
    assert state.attributes.get("is_volume_muted")


async def test_entity_play_media(hass: HomeAssistantType):
    """Test playing media."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    # Play_media
    await common.async_play_media(hass, "audio", "best.mp3", entity_id)
    chromecast.media_controller.play_media.assert_called_once_with("best.mp3", "audio")


async def test_entity_play_media_cast(hass: HomeAssistantType, quick_play_mock):
    """Test playing media with cast special features."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    # Play_media - cast with app ID
    await common.async_play_media(hass, "cast", '{"app_id": "abc123"}', entity_id)
    chromecast.start_app.assert_called_once_with("abc123")

    # Play_media - cast with app name (quick play)
    await common.async_play_media(hass, "cast", '{"app_name": "youtube"}', entity_id)
    quick_play_mock.assert_called_once_with(ANY, "youtube", {})


async def test_entity_play_media_cast_invalid(hass, caplog, quick_play_mock):
    """Test playing media."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    # play_media - media_type cast with invalid JSON
    with pytest.raises(json.decoder.JSONDecodeError):
        await common.async_play_media(hass, "cast", '{"app_id": "abc123"', entity_id)
    assert "Invalid JSON in media_content_id" in caplog.text
    chromecast.start_app.assert_not_called()
    quick_play_mock.assert_not_called()

    # Play_media - media_type cast with extra keys
    await common.async_play_media(
        hass, "cast", '{"app_id": "abc123", "extra": "data"}', entity_id
    )
    assert "Extra keys dict_keys(['extra']) were ignored" in caplog.text
    chromecast.start_app.assert_called_once_with("abc123")
    quick_play_mock.assert_not_called()

    # Play_media - media_type cast with unsupported app
    quick_play_mock.side_effect = NotImplementedError()
    await common.async_play_media(hass, "cast", '{"app_name": "unknown"}', entity_id)
    quick_play_mock.assert_called_once_with(ANY, "unknown", {})
    assert "App unknown not supported" in caplog.text


async def test_entity_play_media_sign_URL(hass: HomeAssistantType):
    """Test playing media."""
    entity_id = "media_player.speaker"

    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com:8123"},
    )

    info = get_fake_chromecast_info()

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # Play_media
    await common.async_play_media(hass, "audio", "/best.mp3", entity_id)
    chromecast.media_controller.play_media.assert_called_once_with(ANY, "audio")
    assert chromecast.media_controller.play_media.call_args[0][0].startswith(
        "http://example.com:8123/best.mp3?authSig="
    )


async def test_entity_media_content_type(hass: HomeAssistantType):
    """Test various content types."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    media_status = MagicMock(images=None)
    media_status.media_is_movie = False
    media_status.media_is_musictrack = False
    media_status.media_is_tvshow = False
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("media_content_type") is None

    media_status.media_is_tvshow = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("media_content_type") == "tvshow"

    media_status.media_is_tvshow = False
    media_status.media_is_musictrack = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("media_content_type") == "music"

    media_status.media_is_musictrack = True
    media_status.media_is_movie = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("media_content_type") == "movie"


async def test_entity_control(hass: HomeAssistantType):
    """Test various device and media controls."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    # Turn on
    await common.async_turn_on(hass, entity_id)
    chromecast.play_media.assert_called_once_with(
        "https://www.home-assistant.io/images/cast/splash.png", ANY
    )
    chromecast.quit_app.reset_mock()

    # Turn off
    await common.async_turn_off(hass, entity_id)
    chromecast.quit_app.assert_called_once_with()

    # Mute
    await common.async_mute_volume(hass, True, entity_id)
    chromecast.set_volume_muted.assert_called_once_with(True)

    # Volume
    await common.async_set_volume_level(hass, 0.33, entity_id)
    chromecast.set_volume.assert_called_once_with(0.33)

    # Media play
    await common.async_media_play(hass, entity_id)
    chromecast.media_controller.play.assert_called_once_with()

    # Media pause
    await common.async_media_pause(hass, entity_id)
    chromecast.media_controller.pause.assert_called_once_with()

    # Media previous
    await common.async_media_previous_track(hass, entity_id)
    chromecast.media_controller.queue_prev.assert_not_called()

    # Media next
    await common.async_media_next_track(hass, entity_id)
    chromecast.media_controller.queue_next.assert_not_called()

    # Media seek
    await common.async_media_seek(hass, 123, entity_id)
    chromecast.media_controller.seek.assert_not_called()

    # Enable support for queue and seek
    media_status = MagicMock(images=None)
    media_status.supports_queue_next = True
    media_status.supports_seek = True
    media_status_cb(media_status)
    await hass.async_block_till_done()

    # Media previous
    await common.async_media_previous_track(hass, entity_id)
    chromecast.media_controller.queue_prev.assert_called_once_with()

    # Media next
    await common.async_media_next_track(hass, entity_id)
    chromecast.media_controller.queue_next.assert_called_once_with()

    # Media seek
    await common.async_media_seek(hass, 123, entity_id)
    chromecast.media_controller.seek.assert_called_once_with(123)


async def test_entity_media_states(hass: HomeAssistantType):
    """Test various entity media states."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    media_status = MagicMock(images=None)
    media_status.player_is_playing = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"

    media_status.player_is_playing = False
    media_status.player_is_paused = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "paused"

    media_status.player_is_paused = False
    media_status.player_is_idle = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "idle"

    media_status.player_is_idle = False
    chromecast.is_idle = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    chromecast.is_idle = False
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


async def test_group_media_states(hass, mz_mock):
    """Test media states are read from group if entity has no state."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, media_status_cb, group_media_status_cb = get_status_callbacks(
        chromecast, mz_mock
    )

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    group_media_status = MagicMock(images=None)
    player_media_status = MagicMock(images=None)

    # Player has no state, group is playing -> Should report 'playing'
    group_media_status.player_is_playing = True
    group_media_status_cb(str(FakeGroupUUID), group_media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"

    # Player is paused, group is playing -> Should report 'paused'
    player_media_status.player_is_playing = False
    player_media_status.player_is_paused = True
    media_status_cb(player_media_status)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "paused"

    # Player is in unknown state, group is playing -> Should report 'playing'
    player_media_status.player_state = "UNKNOWN"
    media_status_cb(player_media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"


async def test_group_media_control(hass, mz_mock):
    """Test media states are read from group if entity has no state."""
    entity_id = "media_player.speaker"
    reg = await hass.helpers.entity_registry.async_get_registry()

    info = get_fake_chromecast_info()
    full_info = attr.evolve(
        info, model_name="google home", friendly_name="Speaker", uuid=FakeUUID
    )

    chromecast = await async_setup_media_player_cast(hass, info)

    _, conn_status_cb, media_status_cb, group_media_status_cb = get_status_callbacks(
        chromecast, mz_mock
    )

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unknown"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", full_info.uuid)

    group_media_status = MagicMock(images=None)
    player_media_status = MagicMock(images=None)

    # Player has no state, group is playing -> Should forward calls to group
    group_media_status.player_is_playing = True
    group_media_status_cb(str(FakeGroupUUID), group_media_status)
    await common.async_media_play(hass, entity_id)
    grp_media = mz_mock.get_multizone_mediacontroller(str(FakeGroupUUID))
    assert grp_media.play.called
    assert not chromecast.media_controller.play.called

    # Player is paused, group is playing -> Should not forward
    player_media_status.player_is_playing = False
    player_media_status.player_is_paused = True
    media_status_cb(player_media_status)
    await common.async_media_pause(hass, entity_id)
    grp_media = mz_mock.get_multizone_mediacontroller(str(FakeGroupUUID))
    assert not grp_media.pause.called
    assert chromecast.media_controller.pause.called

    # Player is in unknown state, group is playing -> Should forward to group
    player_media_status.player_state = "UNKNOWN"
    media_status_cb(player_media_status)
    await common.async_media_stop(hass, entity_id)
    grp_media = mz_mock.get_multizone_mediacontroller(str(FakeGroupUUID))
    assert grp_media.stop.called
    assert not chromecast.media_controller.stop.called

    # Verify play_media is not forwarded
    await common.async_play_media(hass, "music", "best.mp3", entity_id)
    assert not grp_media.play_media.called
    assert chromecast.media_controller.play_media.called


async def test_failed_cast_on_idle(hass, caplog):
    """Test no warning when unless player went idle with reason "ERROR"."""
    info = get_fake_chromecast_info()
    chromecast = await async_setup_media_player_cast(hass, info)
    _, _, media_status_cb = get_status_callbacks(chromecast)

    media_status = MagicMock(images=None)
    media_status.player_is_idle = False
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.com:8123/tts.mp3"
    media_status_cb(media_status)
    assert "Failed to cast media" not in caplog.text

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "Other"
    media_status.content_id = "http://example.com:8123/tts.mp3"
    media_status_cb(media_status)
    assert "Failed to cast media" not in caplog.text

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.com:8123/tts.mp3"
    media_status_cb(media_status)
    assert "Failed to cast media http://example.com:8123/tts.mp3." in caplog.text


async def test_failed_cast_other_url(hass, caplog):
    """Test warning when casting from internal_url fails."""
    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(
            hass,
            tts.DOMAIN,
            {tts.DOMAIN: {"platform": "demo", "base_url": "http://example.local:8123"}},
        )

    info = get_fake_chromecast_info()
    chromecast = await async_setup_media_player_cast(hass, info)
    _, _, media_status_cb = get_status_callbacks(chromecast)

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.com:8123/tts.mp3"
    media_status_cb(media_status)
    assert "Failed to cast media http://example.com:8123/tts.mp3." in caplog.text


async def test_failed_cast_internal_url(hass, caplog):
    """Test warning when casting from internal_url fails."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(
            hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "demo"}}
        )

    info = get_fake_chromecast_info()
    chromecast = await async_setup_media_player_cast(hass, info)
    _, _, media_status_cb = get_status_callbacks(chromecast)

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.local:8123/tts.mp3"
    media_status_cb(media_status)
    assert (
        "Failed to cast media http://example.local:8123/tts.mp3 from internal_url"
        in caplog.text
    )


async def test_failed_cast_external_url(hass, caplog):
    """Test warning when casting from external_url fails."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com:8123"},
    )
    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(
            hass,
            tts.DOMAIN,
            {tts.DOMAIN: {"platform": "demo", "base_url": "http://example.com:8123"}},
        )

    info = get_fake_chromecast_info()
    chromecast = await async_setup_media_player_cast(hass, info)
    _, _, media_status_cb = get_status_callbacks(chromecast)

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.com:8123/tts.mp3"
    media_status_cb(media_status)
    assert (
        "Failed to cast media http://example.com:8123/tts.mp3 from external_url"
        in caplog.text
    )


async def test_failed_cast_tts_base_url(hass, caplog):
    """Test warning when casting from tts.base_url fails."""
    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(
            hass,
            tts.DOMAIN,
            {tts.DOMAIN: {"platform": "demo", "base_url": "http://example.local:8123"}},
        )

    info = get_fake_chromecast_info()
    chromecast = await async_setup_media_player_cast(hass, info)
    _, _, media_status_cb = get_status_callbacks(chromecast)

    media_status = MagicMock(images=None)
    media_status.player_is_idle = True
    media_status.idle_reason = "ERROR"
    media_status.content_id = "http://example.local:8123/tts.mp3"
    media_status_cb(media_status)
    assert (
        "Failed to cast media http://example.local:8123/tts.mp3 from tts.base_url"
        in caplog.text
    )


async def test_disconnect_on_stop(hass: HomeAssistantType):
    """Test cast device disconnects socket on stop."""
    info = get_fake_chromecast_info()

    chromecast = await async_setup_media_player_cast(hass, info)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert chromecast.disconnect.call_count == 1


async def test_entry_setup_no_config(hass: HomeAssistantType):
    """Test setting up entry with no config.."""
    await async_setup_component(hass, "cast", {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cast.media_player._async_setup_platform",
    ) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == {}


async def test_entry_setup_single_config(hass: HomeAssistantType):
    """Test setting up entry and having a single config option."""
    await async_setup_component(
        hass, "cast", {"cast": {"media_player": {"uuid": "bla"}}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cast.media_player._async_setup_platform",
    ) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == {"uuid": "bla"}


async def test_entry_setup_list_config(hass: HomeAssistantType):
    """Test setting up entry and having multiple config options."""
    await async_setup_component(
        hass, "cast", {"cast": {"media_player": [{"uuid": "bla"}, {"uuid": "blu"}]}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cast.media_player._async_setup_platform",
    ) as mock_setup:
        await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 2
    assert mock_setup.mock_calls[0][1][1] == {"uuid": "bla"}
    assert mock_setup.mock_calls[1][1][1] == {"uuid": "blu"}


async def test_entry_setup_platform_not_ready(hass: HomeAssistantType):
    """Test failed setting up entry will raise PlatformNotReady."""
    await async_setup_component(
        hass, "cast", {"cast": {"media_player": {"uuid": "bla"}}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cast.media_player._async_setup_platform",
        side_effect=Exception,
    ) as mock_setup:
        with pytest.raises(PlatformNotReady):
            await cast.async_setup_entry(hass, MockConfigEntry(), None)

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == {"uuid": "bla"}

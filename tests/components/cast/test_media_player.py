"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
from __future__ import annotations

import asyncio
import json
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import attr
import pychromecast
from pychromecast.const import CAST_TYPE_CHROMECAST, CAST_TYPE_GROUP
import pytest
import yarl

from homeassistant.components import media_player, tts
from homeassistant.components.cast import media_player as cast
from homeassistant.components.cast.media_player import ChromecastInfo
from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CAST_APP_ID_HOMEASSISTANT_LOVELACE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er, network
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    load_fixture,
    mock_platform,
)
from tests.components.media_player import common

# pylint: disable=invalid-name
FakeUUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e2")
FakeUUID2 = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e4")
FakeGroupUUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e3")

FAKE_HOST_SERVICE = pychromecast.discovery.ServiceInfo(
    pychromecast.const.SERVICE_TYPE_HOST, ("127.0.0.1", 8009)
)
FAKE_MDNS_SERVICE = pychromecast.discovery.ServiceInfo(
    pychromecast.const.SERVICE_TYPE_MDNS, "the-service"
)

UNDEFINED = object()


def get_fake_chromecast(info: ChromecastInfo):
    """Generate a Fake Chromecast object with the specified arguments."""
    mock = MagicMock(uuid=info.uuid)
    mock.app_id = None
    mock.media_controller.status = None
    return mock


def get_fake_chromecast_info(
    *,
    host="192.168.178.42",
    port=8009,
    service=None,
    uuid: UUID | None = FakeUUID,
    cast_type=UNDEFINED,
    manufacturer=UNDEFINED,
    model_name=UNDEFINED,
):
    """Generate a Fake ChromecastInfo with the specified arguments."""

    if service is None:
        service = pychromecast.discovery.ServiceInfo(
            pychromecast.const.SERVICE_TYPE_HOST, (host, port)
        )
    if cast_type is UNDEFINED:
        cast_type = CAST_TYPE_GROUP if port != 8009 else CAST_TYPE_CHROMECAST
    if manufacturer is UNDEFINED:
        manufacturer = "Nabu Casa"
    if model_name is UNDEFINED:
        model_name = "Chromecast"
    return ChromecastInfo(
        cast_info=pychromecast.models.CastInfo(
            services={service},
            uuid=uuid,
            model_name=model_name,
            friendly_name="Speaker",
            host=host,
            port=port,
            cast_type=cast_type,
            manufacturer=manufacturer,
        )
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
    data = {**{"ignore_cec": [], "known_hosts": [], "uuid": []}, **config}
    with patch(
        "homeassistant.helpers.entity_platform.EntityPlatform._async_schedule_add_entities_for_entry"
    ) as add_entities:
        entry = MockConfigEntry(data=data, domain="cast")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return add_entities


async def async_setup_cast_internal_discovery(hass, config=None):
    """Set up the cast platform and the discovery."""
    browser = MagicMock(devices={}, zc={})

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.discovery.CastBrowser",
        return_value=browser,
    ) as cast_browser:
        add_entities = await async_setup_cast(hass, config)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert browser.start_discovery.call_count == 1

        discovery_callback = cast_browser.call_args[0][0].add_cast
        remove_callback = cast_browser.call_args[0][0].remove_cast

    def discover_chromecast(
        service: pychromecast.discovery.ServiceInfo, info: ChromecastInfo
    ) -> None:
        """Discover a chromecast device."""
        browser.devices[info.uuid] = pychromecast.discovery.CastInfo(
            {service},
            info.uuid,
            info.cast_info.model_name,
            info.friendly_name,
            info.cast_info.host,
            info.cast_info.port,
            info.cast_info.cast_type,
            info.cast_info.manufacturer,
        )
        discovery_callback(info.uuid, "")

    def remove_chromecast(service_name: str, info: ChromecastInfo) -> None:
        """Remove a chromecast device."""
        remove_callback(
            info.uuid,
            service_name,
            pychromecast.models.CastInfo(
                set(),
                info.uuid,
                info.cast_info.model_name,
                info.cast_info.friendly_name,
                info.cast_info.host,
                info.cast_info.port,
                info.cast_info.cast_type,
                info.cast_info.manufacturer,
            ),
        )

    return discover_chromecast, remove_chromecast, add_entities


async def async_setup_media_player_cast(hass: HomeAssistant, info: ChromecastInfo):
    """Set up the cast platform with async_setup_component."""
    browser = MagicMock(devices={}, zc={})
    chromecast = get_fake_chromecast(info)
    zconf = get_fake_zconf(host=info.cast_info.host, port=info.cast_info.port)

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.get_chromecast_from_cast_info",
        return_value=chromecast,
    ) as get_chromecast, patch(
        "homeassistant.components.cast.discovery.pychromecast.discovery.CastBrowser",
        return_value=browser,
    ) as cast_browser, patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf,
    ):
        await async_setup_component(
            hass, "cast", {"cast": {"media_player": {"uuid": info.uuid}}}
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        discovery_callback = cast_browser.call_args[0][0].add_cast

        browser.devices[info.uuid] = pychromecast.discovery.CastInfo(
            {FAKE_MDNS_SERVICE},
            info.uuid,
            info.cast_info.model_name,
            info.friendly_name,
            info.cast_info.host,
            info.cast_info.port,
            info.cast_info.cast_type,
            info.cast_info.manufacturer,
        )
        discovery_callback(info.uuid, FAKE_MDNS_SERVICE[1])

        await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert get_chromecast.call_count == 1

        def discover_chromecast(service_name: str, info: ChromecastInfo) -> None:
            """Discover a chromecast device."""
            browser.devices[info.uuid] = pychromecast.discovery.CastInfo(
                {FAKE_MDNS_SERVICE},
                info.uuid,
                info.cast_info.model_name,
                info.friendly_name,
                info.cast_info.host,
                info.cast_info.port,
                info.cast_info.cast_type,
                info.cast_info.manufacturer,
            )
            discovery_callback(info.uuid, FAKE_MDNS_SERVICE[1])

        return chromecast, discover_chromecast


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


async def test_start_discovery_called_once(hass, castbrowser_mock):
    """Test pychromecast.start_discovery called exactly once."""
    await async_setup_cast(hass)
    assert castbrowser_mock.return_value.start_discovery.call_count == 1

    await async_setup_cast(hass)
    assert castbrowser_mock.return_value.start_discovery.call_count == 1


async def test_internal_discovery_callback_fill_out_group_fail(
    hass, get_multizone_status_mock
):
    """Test internal discovery automatically filling out information."""
    discover_cast, _, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info(host="host1", port=12345, service=FAKE_MDNS_SERVICE)
    zconf = get_fake_zconf(host="host1", port=12345)
    full_info = attr.evolve(
        info,
        cast_info=pychromecast.discovery.CastInfo(
            services=info.cast_info.services,
            uuid=FakeUUID,
            model_name="Chromecast",
            friendly_name="Speaker",
            host=info.cast_info.host,
            port=info.cast_info.port,
            cast_type=info.cast_info.cast_type,
            manufacturer=info.cast_info.manufacturer,
        ),
        is_dynamic_group=False,
    )

    get_multizone_status_mock.assert_not_called()
    get_multizone_status_mock.return_value = None

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf,
    ):
        signal = MagicMock()

        async_dispatcher_connect(hass, "cast_discovered", signal)
        discover_cast(FAKE_MDNS_SERVICE, info)
        await hass.async_block_till_done()

        # when called with incomplete info, it should use HTTP to get missing
        discover = signal.mock_calls[-1][1][0]
        assert discover == full_info
        get_multizone_status_mock.assert_called_once()


async def test_internal_discovery_callback_fill_out_group(
    hass, get_multizone_status_mock
):
    """Test internal discovery automatically filling out information."""
    discover_cast, _, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info(host="host1", port=12345, service=FAKE_MDNS_SERVICE)
    zconf = get_fake_zconf(host="host1", port=12345)
    full_info = attr.evolve(
        info,
        cast_info=pychromecast.discovery.CastInfo(
            services=info.cast_info.services,
            uuid=FakeUUID,
            model_name="Chromecast",
            friendly_name="Speaker",
            host=info.cast_info.host,
            port=info.cast_info.port,
            cast_type=info.cast_info.cast_type,
            manufacturer=info.cast_info.manufacturer,
        ),
        is_dynamic_group=False,
    )

    get_multizone_status_mock.assert_not_called()
    get_multizone_status_mock.return_value = None

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf,
    ):
        signal = MagicMock()

        async_dispatcher_connect(hass, "cast_discovered", signal)
        discover_cast(FAKE_MDNS_SERVICE, info)
        await hass.async_block_till_done()

        # when called with incomplete info, it should use HTTP to get missing
        discover = signal.mock_calls[-1][1][0]
        assert discover == full_info
        get_multizone_status_mock.assert_called_once()


async def test_internal_discovery_callback_fill_out_cast_type_manufacturer(
    hass, get_cast_type_mock, caplog
):
    """Test internal discovery automatically filling out information."""
    discover_cast, _, _ = await async_setup_cast_internal_discovery(hass)
    info = get_fake_chromecast_info(
        host="host1",
        port=8009,
        service=FAKE_MDNS_SERVICE,
        cast_type=None,
        manufacturer=None,
    )
    info2 = get_fake_chromecast_info(
        host="host1",
        port=8009,
        service=FAKE_MDNS_SERVICE,
        cast_type=None,
        manufacturer=None,
        model_name="Model 101",
    )
    zconf = get_fake_zconf(host="host1", port=8009)
    full_info = attr.evolve(
        info,
        cast_info=pychromecast.discovery.CastInfo(
            services=info.cast_info.services,
            uuid=FakeUUID,
            model_name="Chromecast",
            friendly_name="Speaker",
            host=info.cast_info.host,
            port=info.cast_info.port,
            cast_type="audio",
            manufacturer="TrollTech",
        ),
        is_dynamic_group=None,
    )
    full_info2 = attr.evolve(
        info2,
        cast_info=pychromecast.discovery.CastInfo(
            services=info.cast_info.services,
            uuid=FakeUUID,
            model_name="Model 101",
            friendly_name="Speaker",
            host=info.cast_info.host,
            port=info.cast_info.port,
            cast_type="cast",
            manufacturer="Cyberdyne Systems",
        ),
        is_dynamic_group=None,
    )

    get_cast_type_mock.assert_not_called()
    get_cast_type_mock.return_value = full_info.cast_info

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf,
    ):
        signal = MagicMock()

        async_dispatcher_connect(hass, "cast_discovered", signal)
        discover_cast(FAKE_MDNS_SERVICE, info)
        await hass.async_block_till_done()

        # when called with incomplete info, it should use HTTP to get missing
        get_cast_type_mock.assert_called_once()
        assert get_cast_type_mock.call_count == 1
        discover = signal.mock_calls[2][1][0]
        assert discover == full_info
        assert "Fetched cast details for unknown model 'Chromecast'" in caplog.text

        signal.reset_mock()
        # Call again, the model name should be fetched from cache
        discover_cast(FAKE_MDNS_SERVICE, info)
        await hass.async_block_till_done()
        assert get_cast_type_mock.call_count == 1  # No additional calls
        discover = signal.mock_calls[0][1][0]
        assert discover == full_info

        signal.reset_mock()
        # Call for another model, need to call HTTP again
        get_cast_type_mock.return_value = full_info2.cast_info
        discover_cast(FAKE_MDNS_SERVICE, info2)
        await hass.async_block_till_done()
        assert get_cast_type_mock.call_count == 2
        discover = signal.mock_calls[0][1][0]
        assert discover == full_info2


async def test_stop_discovery_called_on_stop(hass, castbrowser_mock):
    """Test pychromecast.stop_discovery called on shutdown."""
    # start_discovery should be called with empty config
    await async_setup_cast(hass, {})
    assert castbrowser_mock.return_value.start_discovery.call_count == 1

    # stop discovery should be called on shutdown
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert castbrowser_mock.return_value.stop_discovery.call_count == 1


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


async def test_manual_cast_chromecasts_uuid(hass):
    """Test only wanted casts are added for manual configuration."""
    cast_1 = get_fake_chromecast_info(host="host_1", uuid=FakeUUID)
    cast_2 = get_fake_chromecast_info(host="host_2", uuid=FakeUUID2)
    zconf_1 = get_fake_zconf(host="host_1")
    zconf_2 = get_fake_zconf(host="host_2")

    # Manual configuration of media player with host "configured_host"
    discover_cast, _, add_dev1 = await async_setup_cast_internal_discovery(
        hass, config={"uuid": str(FakeUUID)}
    )
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service2"
            ),
            cast_2,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 0

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service1"
            ),
            cast_1,
        )
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
    discover_cast, _, add_dev1 = await async_setup_cast_internal_discovery(hass)
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service2"
            ),
            cast_2,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service1"
            ),
            cast_1,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 2


async def test_discover_dynamic_group(
    hass, get_multizone_status_mock, get_chromecast_mock, caplog
):
    """Test dynamic group does not create device or entity."""
    cast_1 = get_fake_chromecast_info(host="host_1", port=23456, uuid=FakeUUID)
    cast_2 = get_fake_chromecast_info(host="host_2", port=34567, uuid=FakeUUID2)
    zconf_1 = get_fake_zconf(host="host_1", port=23456)
    zconf_2 = get_fake_zconf(host="host_2", port=34567)

    reg = er.async_get(hass)

    # Fake dynamic group info
    tmp1 = MagicMock()
    tmp1.uuid = FakeUUID
    tmp2 = MagicMock()
    tmp2.uuid = FakeUUID2
    get_multizone_status_mock.return_value.dynamic_groups = [tmp1, tmp2]

    get_chromecast_mock.assert_not_called()
    discover_cast, remove_cast, add_dev1 = await async_setup_cast_internal_discovery(
        hass
    )

    tasks = []
    real_create_task = asyncio.create_task

    def create_task(*args, **kwargs):
        tasks.append(real_create_task(*args, **kwargs))

    # Discover cast service
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ), patch(
        "homeassistant.components.cast.media_player.asyncio.create_task",
        wraps=create_task,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service"
            ),
            cast_1,
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()  # having tasks that add jobs

    assert len(tasks) == 1
    await asyncio.gather(*tasks)
    tasks.clear()
    get_chromecast_mock.assert_called()
    get_chromecast_mock.reset_mock()
    assert add_dev1.call_count == 0
    assert reg.async_get_entity_id("media_player", "cast", cast_1.uuid) is None

    # Discover other dynamic group cast service
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ), patch(
        "homeassistant.components.cast.media_player.asyncio.create_task",
        wraps=create_task,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service"
            ),
            cast_2,
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()  # having tasks that add jobs

    assert len(tasks) == 1
    await asyncio.gather(*tasks)
    tasks.clear()
    get_chromecast_mock.assert_called()
    get_chromecast_mock.reset_mock()
    assert add_dev1.call_count == 0
    assert reg.async_get_entity_id("media_player", "cast", cast_2.uuid) is None

    # Get update for cast service
    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ), patch(
        "homeassistant.components.cast.media_player.asyncio.create_task",
        wraps=create_task,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service"
            ),
            cast_1,
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()  # having tasks that add jobs

    assert len(tasks) == 0
    get_chromecast_mock.assert_not_called()
    assert add_dev1.call_count == 0
    assert reg.async_get_entity_id("media_player", "cast", cast_1.uuid) is None

    # Remove cast service
    assert "Disconnecting from chromecast" not in caplog.text

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        remove_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service"
            ),
            cast_1,
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()  # having tasks that add jobs

    assert "Disconnecting from chromecast" in caplog.text


async def test_update_cast_chromecasts(hass):
    """Test discovery of same UUID twice only adds one cast."""
    cast_1 = get_fake_chromecast_info(host="old_host")
    cast_2 = get_fake_chromecast_info(host="new_host")
    zconf_1 = get_fake_zconf(host="old_host")
    zconf_2 = get_fake_zconf(host="new_host")

    # Manual configuration of media player with host "configured_host"
    discover_cast, _, add_dev1 = await async_setup_cast_internal_discovery(hass)

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_1,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service1"
            ),
            cast_1,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1

    with patch(
        "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        return_value=zconf_2,
    ):
        discover_cast(
            pychromecast.discovery.ServiceInfo(
                pychromecast.const.SERVICE_TYPE_MDNS, "service2"
            ),
            cast_2,
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # having tasks that add jobs
    assert add_dev1.call_count == 1


async def test_entity_availability(hass: HomeAssistant):
    """Test handling of connection status."""
    entity_id = "media_player.speaker"
    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    connection_status = MagicMock()
    connection_status.status = "LOST"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    connection_status = MagicMock()
    connection_status.status = "DISCONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    # Can't reconnect after receiving DISCONNECTED
    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unavailable"


@pytest.mark.parametrize("port,entry_type", ((8009, None), (12345, None)))
async def test_device_registry(hass: HomeAssistant, hass_ws_client, port, entry_type):
    """Test device registry integration."""
    assert await async_setup_component(hass, "config", {})

    entity_id = "media_player.speaker"
    reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    info = get_fake_chromecast_info(port=port)

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    chromecast.cast_type = pychromecast.const.CAST_TYPE_CHROMECAST
    _, conn_status_cb, _ = get_status_callbacks(chromecast)
    cast_entry = hass.config_entries.async_entries("cast")[0]

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))
    entity_entry = reg.async_get(entity_id)
    device_entry = dev_reg.async_get(entity_entry.device_id)
    assert entity_entry.device_id == device_entry.id
    assert device_entry.entry_type == entry_type

    # Check that the chromecast object is torn down when the device is removed
    chromecast.disconnect.assert_not_called()

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": cast_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    chromecast.disconnect.assert_called_once()

    assert reg.async_get(entity_id) is None
    assert dev_reg.async_get(entity_entry.device_id) is None


async def test_entity_cast_status(hass: HomeAssistant):
    """Test handling of cast status."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    chromecast.cast_type = pychromecast.const.CAST_TYPE_CHROMECAST
    cast_status_cb, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    # No media status, pause, play, stop not supported
    assert state.attributes.get("supported_features") == (
        SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
    )

    cast_status = MagicMock()
    cast_status.volume_level = 0.5
    cast_status.volume_muted = False
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    # Volume hidden if no app is active
    assert state.attributes.get("volume_level") is None
    assert not state.attributes.get("is_volume_muted")

    chromecast.app_id = "1234"
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

    # Disable support for volume control
    cast_status = MagicMock()
    cast_status.volume_control_type = "fixed"
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("supported_features") == (
        SUPPORT_PLAY_MEDIA | SUPPORT_TURN_OFF | SUPPORT_TURN_ON
    )


@pytest.mark.parametrize(
    "cast_type,supported_features,supported_features_no_media",
    [
        (
            pychromecast.const.CAST_TYPE_AUDIO,
            SUPPORT_PAUSE
            | SUPPORT_PLAY
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_STOP
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
            SUPPORT_PLAY_MEDIA
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
        ),
        (
            pychromecast.const.CAST_TYPE_CHROMECAST,
            SUPPORT_PAUSE
            | SUPPORT_PLAY
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_STOP
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
            SUPPORT_PLAY_MEDIA
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
        ),
        (
            pychromecast.const.CAST_TYPE_GROUP,
            SUPPORT_PAUSE
            | SUPPORT_PLAY
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_STOP
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
            SUPPORT_PLAY_MEDIA
            | SUPPORT_TURN_OFF
            | SUPPORT_TURN_ON
            | SUPPORT_VOLUME_MUTE
            | SUPPORT_VOLUME_SET,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant, cast_type, supported_features, supported_features_no_media
):
    """Test supported features."""
    entity_id = "media_player.speaker"

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    chromecast.cast_type = cast_type
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert state.attributes.get("supported_features") == supported_features_no_media

    media_status = MagicMock(images=None)
    media_status.supports_queue_next = False
    media_status.supports_seek = False
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes.get("supported_features") == supported_features


async def test_entity_browse_media(hass: HomeAssistant, hass_ws_client):
    """Test we can browse media."""
    await async_setup_component(hass, "media_source", {"media_source": {}})

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.speaker",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child_1 = {
        "title": "Epic Sax Guy 10 Hours.mp4",
        "media_class": "video",
        "media_content_type": "video/mp4",
        "media_content_id": "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4",
        "can_play": True,
        "can_expand": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_1 in response["result"]["children"]

    expected_child_2 = {
        "title": "test.mp3",
        "media_class": "music",
        "media_content_type": "audio/mpeg",
        "media_content_id": "media-source://media_source/local/test.mp3",
        "can_play": True,
        "can_expand": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_2 in response["result"]["children"]


@pytest.mark.parametrize(
    "cast_type",
    [pychromecast.const.CAST_TYPE_AUDIO, pychromecast.const.CAST_TYPE_GROUP],
)
async def test_entity_browse_media_audio_only(
    hass: HomeAssistant, hass_ws_client, cast_type
):
    """Test we can browse media."""
    await async_setup_component(hass, "media_source", {"media_source": {}})

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    chromecast.cast_type = cast_type
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.speaker",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child_1 = {
        "title": "Epic Sax Guy 10 Hours.mp4",
        "media_class": "video",
        "media_content_type": "video/mp4",
        "media_content_id": "media-source://media_source/local/Epic Sax Guy 10 Hours.mp4",
        "can_play": True,
        "can_expand": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_1 not in response["result"]["children"]

    expected_child_2 = {
        "title": "test.mp3",
        "media_class": "music",
        "media_content_type": "audio/mpeg",
        "media_content_id": "media-source://media_source/local/test.mp3",
        "can_play": True,
        "can_expand": False,
        "thumbnail": None,
        "children_media_class": None,
    }
    assert expected_child_2 in response["result"]["children"]


async def test_entity_play_media(hass: HomeAssistant, quick_play_mock):
    """Test playing media."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    # Play_media
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "audio",
            media_player.ATTR_MEDIA_CONTENT_ID: "http://example.com/best.mp3",
            media_player.ATTR_MEDIA_EXTRA: {"metadata": {"metadatatype": 3}},
        },
        blocking=True,
    )

    chromecast.media_controller.play_media.assert_not_called()
    quick_play_mock.assert_called_once_with(
        chromecast,
        "default_media_receiver",
        {
            "media_id": "http://example.com/best.mp3",
            "media_type": "audio",
            "metadata": {"metadatatype": 3},
        },
    )


async def test_entity_play_media_cast(hass: HomeAssistant, quick_play_mock):
    """Test playing media with cast special features."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    # Play_media - cast with app ID
    await common.async_play_media(hass, "cast", '{"app_id": "abc123"}', entity_id)
    chromecast.start_app.assert_called_once_with("abc123")

    # Play_media - cast with app name (quick play)
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "cast",
            media_player.ATTR_MEDIA_CONTENT_ID: '{"app_name":"youtube"}',
            media_player.ATTR_MEDIA_EXTRA: {"metadata": {"metadatatype": 3}},
        },
        blocking=True,
    )
    quick_play_mock.assert_called_once_with(
        ANY, "youtube", {"metadata": {"metadatatype": 3}}
    )


async def test_entity_play_media_cast_invalid(hass, caplog, quick_play_mock):
    """Test playing media."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

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


async def test_entity_play_media_sign_URL(hass: HomeAssistant, quick_play_mock):
    """Test playing media."""
    entity_id = "media_player.speaker"

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.com:8123"},
    )

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # Play_media
    await common.async_play_media(hass, "audio", "/best.mp3", entity_id)
    quick_play_mock.assert_called_once_with(
        chromecast, "default_media_receiver", {"media_id": ANY, "media_type": "audio"}
    )
    assert quick_play_mock.call_args[0][2]["media_id"].startswith(
        "http://example.com:8123/best.mp3?authSig="
    )


@pytest.mark.parametrize(
    "url,fixture,playlist_item",
    (
        # Test title is extracted from m3u playlist
        (
            "https://sverigesradio.se/topsy/direkt/209-hi-mp3.m3u",
            "209-hi-mp3.m3u",
            {
                "media_id": "https://http-live.sr.se/p4norrbotten-mp3-192",
                "media_type": "audio",
                "metadata": {"title": "Sveriges Radio"},
            },
        ),
        # Test title is extracted from pls playlist
        (
            "http://sverigesradio.se/topsy/direkt/164-hi-aac.pls",
            "164-hi-aac.pls",
            {
                "media_id": "https://http-live.sr.se/p3-aac-192",
                "media_type": "audio",
                "metadata": {"title": "Sveriges Radio"},
            },
        ),
        # Test HLS playlist is forwarded to the device
        (
            "http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/nonuk/sbr_low/ak/bbc_radio_fourfm.m3u8",
            "bbc_radio_fourfm.m3u8",
            {
                "media_id": "http://a.files.bbci.co.uk/media/live/manifesto/audio/simulcast/hls/nonuk/sbr_low/ak/bbc_radio_fourfm.m3u8",
                "media_type": "audio",
            },
        ),
        # Test bad playlist is forwarded to the device
        (
            "https://sverigesradio.se/209-hi-mp3.m3u",
            "209-hi-mp3_bad_url.m3u",
            {
                "media_id": "https://sverigesradio.se/209-hi-mp3.m3u",
                "media_type": "audio",
            },
        ),
    ),
)
async def test_entity_play_media_playlist(
    hass: HomeAssistant, aioclient_mock, quick_play_mock, url, fixture, playlist_item
):
    """Test playing media."""
    entity_id = "media_player.speaker"
    aioclient_mock.get(url, text=load_fixture(fixture, "cast"))

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.com:8123"},
    )

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # Play_media
    await common.async_play_media(hass, "audio", url, entity_id)
    quick_play_mock.assert_called_once_with(
        chromecast,
        "default_media_receiver",
        playlist_item,
    )


async def test_entity_media_content_type(hass: HomeAssistant):
    """Test various content types."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

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


async def test_entity_control(hass: HomeAssistant, quick_play_mock):
    """Test various device and media controls."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    chromecast.cast_type = pychromecast.const.CAST_TYPE_CHROMECAST
    _, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    # Fake connection status
    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # Fake media status
    media_status = MagicMock(images=None)
    media_status.player_state = "PLAYING"
    media_status.supports_queue_next = False
    media_status.supports_seek = False
    media_status_cb(media_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "playing"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    assert state.attributes.get("supported_features") == (
        SUPPORT_PAUSE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_STOP
        | SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
    )

    # Turn on
    await common.async_turn_on(hass, entity_id)
    quick_play_mock.assert_called_once_with(
        chromecast,
        "default_media_receiver",
        {
            "media_id": "https://www.home-assistant.io/images/cast/splash.png",
            "media_type": "image/png",
        },
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
    with pytest.raises(HomeAssistantError):
        await common.async_media_previous_track(hass, entity_id)
    chromecast.media_controller.queue_prev.assert_not_called()

    # Media next
    with pytest.raises(HomeAssistantError):
        await common.async_media_next_track(hass, entity_id)
    chromecast.media_controller.queue_next.assert_not_called()

    # Media seek
    with pytest.raises(HomeAssistantError):
        await common.async_media_seek(hass, 123, entity_id)
    chromecast.media_controller.seek.assert_not_called()

    # Enable support for queue and seek
    media_status = MagicMock(images=None)
    media_status.supports_queue_next = True
    media_status.supports_seek = True
    media_status_cb(media_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get("supported_features") == (
        SUPPORT_PAUSE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_STOP
        | SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
        | SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_SEEK
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
    )

    # Media previous
    await common.async_media_previous_track(hass, entity_id)
    chromecast.media_controller.queue_prev.assert_called_once_with()

    # Media next
    await common.async_media_next_track(hass, entity_id)
    chromecast.media_controller.queue_next.assert_called_once_with()

    # Media seek
    await common.async_media_seek(hass, 123, entity_id)
    chromecast.media_controller.seek.assert_called_once_with(123)


# Some smart TV's with Google TV report "Netflix", not the Netflix app's ID
@pytest.mark.parametrize(
    "app_id, state_no_media",
    [(pychromecast.APP_YOUTUBE, "idle"), ("Netflix", "playing")],
)
async def test_entity_media_states(hass: HomeAssistant, app_id, state_no_media):
    """Test various entity media states."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    cast_status_cb, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    # App id updated, but no media status
    chromecast.app_id = app_id
    cast_status = MagicMock()
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == state_no_media

    # Got media status
    media_status = MagicMock(images=None)
    media_status.player_state = "BUFFERING"
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "buffering"

    media_status.player_state = "PLAYING"
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"

    media_status.player_state = None
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

    # No media status, app is still running
    media_status_cb(None)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == state_no_media

    # App no longer running
    chromecast.app_id = pychromecast.IDLE_APP_ID
    cast_status = MagicMock()
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # No cast status
    chromecast.is_idle = False
    cast_status_cb(None)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


async def test_entity_media_states_lovelace_app(hass: HomeAssistant):
    """Test various entity media states when the lovelace app is active."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    cast_status_cb, conn_status_cb, media_status_cb = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    chromecast.app_id = CAST_APP_ID_HOMEASSISTANT_LOVELACE
    cast_status = MagicMock()
    cast_status_cb(cast_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"
    assert state.attributes.get("supported_features") == (
        SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_OFF
        | SUPPORT_TURN_ON
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
    )

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
    assert state.state == "playing"

    media_status.player_is_paused = False
    media_status.player_is_idle = True
    media_status_cb(media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"

    chromecast.app_id = pychromecast.IDLE_APP_ID
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
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
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
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    group_media_status = MagicMock(images=None)
    player_media_status = MagicMock(images=None)

    # Player has no state, group is buffering -> Should report 'buffering'
    group_media_status.player_state = "BUFFERING"
    group_media_status_cb(str(FakeGroupUUID), group_media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "buffering"

    # Player has no state, group is playing -> Should report 'playing'
    group_media_status.player_state = "PLAYING"
    group_media_status_cb(str(FakeGroupUUID), group_media_status)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "playing"

    # Player is paused, group is playing -> Should report 'paused'
    player_media_status.player_state = None
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


async def test_group_media_states_early(hass, mz_mock):
    """Test media states are read from group if entity has no state.

    This tests case asserts group state is polled when the player is created.
    """
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    mz_mock.get_multizone_memberships = MagicMock(return_value=[str(FakeGroupUUID)])
    mz_mock.get_multizone_mediacontroller = MagicMock(
        return_value=MagicMock(status=MagicMock(images=None, player_state="BUFFERING"))
    )

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _, _ = get_status_callbacks(chromecast, mz_mock)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == "Speaker"
    assert state.state == "unavailable"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

    # Check group state is polled when player is first created
    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "buffering"

    connection_status = MagicMock()
    connection_status.status = "LOST"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    # Check group state is polled when player reconnects
    mz_mock.get_multizone_mediacontroller = MagicMock(
        return_value=MagicMock(status=MagicMock(images=None, player_state="PLAYING"))
    )

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "playing"


async def test_group_media_control(hass, mz_mock, quick_play_mock):
    """Test media controls are handled by group if entity has no state."""
    entity_id = "media_player.speaker"
    reg = er.async_get(hass)

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)

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
    assert state.state == "off"
    assert entity_id == reg.async_get_entity_id("media_player", "cast", str(info.uuid))

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
    await common.async_play_media(
        hass, "music", "http://example.com/best.mp3", entity_id
    )
    assert not grp_media.play_media.called
    assert not chromecast.media_controller.play_media.called
    quick_play_mock.assert_called_once_with(
        chromecast,
        "default_media_receiver",
        {"media_id": "http://example.com/best.mp3", "media_type": "music"},
    )


async def test_failed_cast_on_idle(hass, caplog):
    """Test no warning when unless player went idle with reason "ERROR"."""
    info = get_fake_chromecast_info()
    chromecast, _ = await async_setup_media_player_cast(hass, info)
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
    chromecast, _ = await async_setup_media_player_cast(hass, info)
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
    chromecast, _ = await async_setup_media_player_cast(hass, info)
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
    chromecast, _ = await async_setup_media_player_cast(hass, info)
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
    chromecast, _ = await async_setup_media_player_cast(hass, info)
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


async def test_disconnect_on_stop(hass: HomeAssistant):
    """Test cast device disconnects socket on stop."""
    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert chromecast.disconnect.call_count == 1


async def test_entry_setup_no_config(hass: HomeAssistant):
    """Test deprecated empty yaml config.."""
    await async_setup_component(hass, "cast", {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries("cast")


async def test_entry_setup_empty_config(hass: HomeAssistant):
    """Test deprecated empty yaml config.."""
    await async_setup_component(hass, "cast", {"cast": {}})
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("cast")[0]
    assert config_entry.data["uuid"] == []
    assert config_entry.data["ignore_cec"] == []


async def test_entry_setup_single_config(hass: HomeAssistant):
    """Test deprecated yaml config with a single config media_player."""
    await async_setup_component(
        hass, "cast", {"cast": {"media_player": {"uuid": "bla", "ignore_cec": "cast1"}}}
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("cast")[0]
    assert config_entry.data["uuid"] == ["bla"]
    assert config_entry.data["ignore_cec"] == ["cast1"]

    assert pychromecast.IGNORE_CEC == ["cast1"]


async def test_entry_setup_list_config(hass: HomeAssistant):
    """Test deprecated yaml config with multiple media_players."""
    await async_setup_component(
        hass,
        "cast",
        {
            "cast": {
                "media_player": [
                    {"uuid": "bla", "ignore_cec": "cast1"},
                    {"uuid": "blu", "ignore_cec": ["cast2", "cast3"]},
                ]
            }
        },
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("cast")[0]
    assert set(config_entry.data["uuid"]) == {"bla", "blu"}
    assert set(config_entry.data["ignore_cec"]) == {"cast1", "cast2", "cast3"}
    assert set(pychromecast.IGNORE_CEC) == {"cast1", "cast2", "cast3"}


async def test_invalid_cast_platform(hass: HomeAssistant, caplog):
    """Test we can play media through a cast platform."""
    cast_platform_mock = Mock()
    del cast_platform_mock.async_get_media_browser_root_object
    del cast_platform_mock.async_browse_media
    del cast_platform_mock.async_play_media
    mock_platform(hass, "test.cast", cast_platform_mock)

    await async_setup_component(hass, "test", {"test": {}})
    await hass.async_block_till_done()

    info = get_fake_chromecast_info()
    await async_setup_media_player_cast(hass, info)

    assert "Invalid cast platform <Mock id" in caplog.text


async def test_cast_platform_play_media(hass: HomeAssistant, quick_play_mock, caplog):
    """Test we can play media through a cast platform."""
    entity_id = "media_player.speaker"

    _can_play = True

    def can_play(*args):
        return _can_play

    cast_platform_mock = Mock(
        async_get_media_browser_root_object=AsyncMock(return_value=[]),
        async_browse_media=AsyncMock(return_value=None),
        async_play_media=AsyncMock(side_effect=can_play),
    )
    mock_platform(hass, "test.cast", cast_platform_mock)

    await async_setup_component(hass, "test", {"test": {}})
    await hass.async_block_till_done()

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    assert "Invalid cast platform <Mock id" not in caplog.text
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # This will play using the cast platform
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "audio",
            media_player.ATTR_MEDIA_CONTENT_ID: "best.mp3",
            media_player.ATTR_MEDIA_EXTRA: {"metadata": {"metadatatype": 3}},
        },
        blocking=True,
    )

    # Assert the media player attempt to play media through the cast platform
    cast_platform_mock.async_play_media.assert_called_once_with(
        hass, entity_id, chromecast, "audio", "best.mp3"
    )

    # Assert pychromecast is not used to play media
    chromecast.media_controller.play_media.assert_not_called()
    quick_play_mock.assert_not_called()

    # This will not play using the cast platform
    _can_play = False
    cast_platform_mock.async_play_media.reset_mock()
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "audio",
            media_player.ATTR_MEDIA_CONTENT_ID: "http://example.com/best.mp3",
            media_player.ATTR_MEDIA_EXTRA: {"metadata": {"metadatatype": 3}},
        },
        blocking=True,
    )

    # Assert the media player attempt to play media through the cast platform
    cast_platform_mock.async_play_media.assert_called_once_with(
        hass, entity_id, chromecast, "audio", "http://example.com/best.mp3"
    )

    # Assert pychromecast is used to play media
    chromecast.media_controller.play_media.assert_not_called()
    quick_play_mock.assert_called()


async def test_cast_platform_browse_media(hass: HomeAssistant, hass_ws_client):
    """Test we can play media through a cast platform."""
    cast_platform_mock = Mock(
        async_get_media_browser_root_object=AsyncMock(
            return_value=[
                BrowseMedia(
                    title="Spotify",
                    media_class=MEDIA_CLASS_APP,
                    media_content_id="",
                    media_content_type="spotify",
                    thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
                    can_play=False,
                    can_expand=True,
                )
            ]
        ),
        async_browse_media=AsyncMock(
            return_value=BrowseMedia(
                title="Spotify Favourites",
                media_class=MEDIA_CLASS_PLAYLIST,
                media_content_id="",
                media_content_type="spotify",
                can_play=True,
                can_expand=False,
            )
        ),
        async_play_media=AsyncMock(return_value=False),
    )
    mock_platform(hass, "test.cast", cast_platform_mock)

    await async_setup_component(hass, "test", {"test": {}})
    await async_setup_component(hass, "media_source", {"media_source": {}})
    await hass.async_block_till_done()

    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.speaker",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child = {
        "title": "Spotify",
        "media_class": "app",
        "media_content_type": "spotify",
        "media_content_id": "",
        "can_play": False,
        "can_expand": True,
        "thumbnail": "https://brands.home-assistant.io/_/spotify/logo.png",
        "children_media_class": None,
    }
    assert expected_child in response["result"]["children"]

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": "media_player.speaker",
            "media_content_id": "",
            "media_content_type": "spotify",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_response = {
        "title": "Spotify Favourites",
        "media_class": "playlist",
        "media_content_type": "spotify",
        "media_content_id": "",
        "can_play": True,
        "can_expand": False,
        "children_media_class": None,
        "thumbnail": None,
        "children": [],
        "not_shown": 0,
    }
    assert response["result"] == expected_response


async def test_cast_platform_play_media_local_media(
    hass: HomeAssistant, quick_play_mock, caplog
):
    """Test we process data when playing local media."""
    entity_id = "media_player.speaker"
    info = get_fake_chromecast_info()

    chromecast, _ = await async_setup_media_player_cast(hass, info)
    _, conn_status_cb, _ = get_status_callbacks(chromecast)

    # Bring Chromecast online
    connection_status = MagicMock()
    connection_status.status = "CONNECTED"
    conn_status_cb(connection_status)
    await hass.async_block_till_done()

    # This will play using the cast platform
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "application/vnd.apple.mpegurl",
            media_player.ATTR_MEDIA_CONTENT_ID: "/api/hls/bla/master_playlist.m3u8",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Assert we added extra play information
    quick_play_mock.assert_called()
    app_data = quick_play_mock.call_args[0][2]

    assert not app_data["media_id"].startswith("/")
    assert "authSig" in yarl.URL(app_data["media_id"]).query
    assert app_data["media_type"] == "application/vnd.apple.mpegurl"
    assert app_data["stream_type"] == "LIVE"
    assert app_data["media_info"] == {
        "hlsVideoSegmentFormat": "fmp4",
    }

    quick_play_mock.reset_mock()

    # Test not appending if we have a signature
    await hass.services.async_call(
        media_player.DOMAIN,
        media_player.SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            media_player.ATTR_MEDIA_CONTENT_TYPE: "application/vnd.apple.mpegurl",
            media_player.ATTR_MEDIA_CONTENT_ID: f"{network.get_url(hass)}/api/hls/bla/master_playlist.m3u8?token=bla",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Assert we added extra play information
    quick_play_mock.assert_called()
    app_data = quick_play_mock.call_args[0][2]
    # No authSig appended
    assert (
        app_data["media_id"]
        == f"{network.get_url(hass)}/api/hls/bla/master_playlist.m3u8?token=bla"
    )

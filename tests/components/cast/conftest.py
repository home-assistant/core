"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
from typing import Optional
from uuid import UUID

import pytest

from homeassistant.components.cast.media_player import ChromecastInfo
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, Mock, patch
from tests.common import MockConfigEntry


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

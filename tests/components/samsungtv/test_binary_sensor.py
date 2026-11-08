"""Tests for Samsung TV Art Mode status."""

from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from samsungtvws.exceptions import ConnectionFailure, ResponseError, UnauthorizedError
from syrupy.assertion import SnapshotAssertion
from websocket import WebSocketException, WebSocketTimeoutException

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.components.samsungtv.const import TIMEOUT_WEBSOCKET, VALUE_CONF_NAME
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_samsungtv_entry
from .const import (
    ENTRYDATA_ENCRYPTED_WEBSOCKET,
    ENTRYDATA_LEGACY,
    ENTRYDATA_WEBSOCKET,
    SAMPLE_DEVICE_INFO_WIFI,
)

ENTITY_ID = "binary_sensor.mock_title_art_mode"
MEDIA_PLAYER_ENTITY_ID = "media_player.mock_title"

pytestmark = pytest.mark.usefixtures("remote_websocket", "art_api")


@pytest.fixture
def frame_tv(rest_api: Mock) -> None:
    """Make the TV report Art Mode support."""
    device_info = deepcopy(SAMPLE_DEVICE_INFO_WIFI)
    device_info["device"]["FrameTVSupport"] = "true"
    rest_api.rest_device_info.return_value = device_info


@pytest.mark.usefixtures("frame_tv")
@pytest.mark.parametrize("status", ["on", "off"])
async def test_art_mode_sensor(
    hass: HomeAssistant,
    art_api: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    status: str,
) -> None:
    """Test Art Mode status and registration with the existing TV device."""
    art_api.get_artmode.return_value = status
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID) == snapshot
    sensor_entry = entity_registry.async_get(ENTITY_ID)
    assert sensor_entry == snapshot
    assert (
        sensor_entry.device_id
        == entity_registry.async_get(MEDIA_PLAYER_ENTITY_ID).device_id
    )


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_updates(
    hass: HomeAssistant, art_api: Mock, freezer: FrozenDateTimeFactory
) -> None:
    """Test periodic updates use the same Art Mode connection."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    art_api.get_artmode.return_value = "off"
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert art_api.get_artmode.call_count == 2
    art_api.close.assert_not_called()


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_connection_options(
    hass: HomeAssistant, art_api_class: Mock
) -> None:
    """Test Art Mode uses the TV's configured port and authentication."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    art_api_class.assert_called_once_with(
        host=ENTRYDATA_WEBSOCKET[CONF_HOST],
        port=ENTRYDATA_WEBSOCKET[CONF_PORT],
        token="FAKE_TOKEN",
        timeout=TIMEOUT_WEBSOCKET,
        key_press_delay=0,
        name=VALUE_CONF_NAME,
    )


@pytest.mark.usefixtures("rest_api", "remote_legacy", "remote_encrypted_websocket")
@pytest.mark.parametrize(
    "entry_data",
    [ENTRYDATA_WEBSOCKET, ENTRYDATA_LEGACY, ENTRYDATA_ENCRYPTED_WEBSOCKET],
    ids=["websocket", "legacy", "encrypted"],
)
async def test_no_art_mode_support(
    hass: HomeAssistant, art_api: Mock, entry_data: dict[str, Any]
) -> None:
    """Test other TVs do not get an Art Mode sensor or Art API requests."""
    await setup_samsungtv_entry(hass, entry_data)

    assert hass.states.get(ENTITY_ID) is None
    art_api.get_artmode.assert_not_called()


@pytest.mark.usefixtures("frame_tv")
@pytest.mark.parametrize(
    "error",
    [
        ConnectionFailure("Disconnected"),
        ResponseError("Unsupported request"),
        UnauthorizedError("Unauthorized"),
        WebSocketException("Disconnected"),
        WebSocketTimeoutException("Timed out"),
        OSError("Connection lost"),
    ],
    ids=["connection", "response", "unauthorized", "websocket", "timeout", "os"],
)
async def test_art_mode_error_and_recovery(
    hass: HomeAssistant,
    art_api: Mock,
    error: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Art API errors affect only the sensor and recover on the next poll."""
    art_api.get_artmode.side_effect = error
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_ON
    art_api.close.assert_called_once()

    art_api.get_artmode.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert art_api.get_artmode.call_count == 2


@pytest.mark.usefixtures("frame_tv")
@pytest.mark.parametrize("status", [None, {}, "unknown"])
async def test_art_mode_invalid_status(
    hass: HomeAssistant, art_api: Mock, status: str | dict[str, str] | None
) -> None:
    """Test unrecognized status is not reported as Art Mode being off."""
    art_api.get_artmode.return_value = status
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_standby(
    hass: HomeAssistant,
    art_api: Mock,
    rest_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test standby closes the Art connection without opening another one."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    rest_api.rest_device_info.return_value["device"]["PowerState"] = "standby"
    for _ in range(2):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    art_api.close.assert_called_once()
    art_api.get_artmode.assert_called_once()


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_starts_in_standby(
    hass: HomeAssistant,
    art_api: Mock,
    rest_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a TV in standby is not woken to query Art Mode."""
    rest_api.rest_device_info.return_value["device"]["PowerState"] = "standby"
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    art_api.get_artmode.assert_not_called()

    rest_api.rest_device_info.return_value["device"]["PowerState"] = "on"
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    art_api.get_artmode.assert_called_once()


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_support_discovered_later(
    hass: HomeAssistant,
    art_api: Mock,
    rest_api: Mock,
    remote_websocket: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a TV unavailable at startup gets exactly one sensor when discovered."""
    rest_api.rest_device_info.side_effect = ResponseError
    remote_websocket.is_alive.return_value = False
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID) is None
    art_api.get_artmode.assert_not_called()

    rest_api.rest_device_info.side_effect = None
    remote_websocket.is_alive.return_value = True
    for _ in range(2):
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(hass.states.async_all("binary_sensor")) == 1


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_power_off(
    hass: HomeAssistant, art_api: Mock, freezer: FrozenDateTimeFactory
) -> None:
    """Test powering off the TV closes Art Mode and stops querying it."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    await hass.services.async_call(
        "media_player",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    art_api.close.assert_called_once()
    art_api.get_artmode.assert_called_once()


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_unload(hass: HomeAssistant, art_api: Mock) -> None:
    """Test unloading the integration closes the Art Mode connection."""
    entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    art_api.close.assert_called_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_token_update(hass: HomeAssistant, art_api: Mock) -> None:
    """Test a refreshed Art API token is saved in the config entry."""

    def get_artmode() -> str:
        art_api.token = "NEW_TOKEN"
        return "on"

    art_api.get_artmode.side_effect = get_artmode
    entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert entry.data[CONF_TOKEN] == "NEW_TOKEN"


@pytest.mark.usefixtures("frame_tv")
async def test_art_mode_preserves_refreshed_remote_token(
    hass: HomeAssistant,
    art_api: Mock,
    remote_websocket: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Art Mode polling preserves the token from a remote reconnect."""
    entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
    assert entry.data[CONF_TOKEN] == art_api.token

    remote_token = "REMOTE_TOKEN"
    remote_websocket.is_alive.return_value = False
    remote_websocket.token = remote_token
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: f"{REMOTE_DOMAIN}.mock_title", ATTR_COMMAND: "KEY_HOME"},
        blocking=True,
    )
    remote_websocket.is_alive.return_value = True
    assert entry.data[CONF_TOKEN] == remote_token

    art_api.get_artmode.return_value = "off"
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert entry.data[CONF_TOKEN] == remote_token

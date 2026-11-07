"""Tests for the SamsungTV binary sensor platform."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    async_load_json_object_fixture,
)
from samsungtvws.exceptions import ConnectionFailure, ResponseError

from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.const import CONF_MAC, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_samsungtv_entry
from .const import ENTRYDATA_LEGACY, ENTRYDATA_WEBSOCKET

ENTITY_ID = "binary_sensor.mock_title_art_mode"


@pytest.fixture(name="frame_rest_api")
async def frame_rest_api_fixture(hass: HomeAssistant, rest_api: Mock) -> Mock:
    """Return a REST API mock reporting a Frame TV."""
    rest_api.rest_device_info.return_value = await async_load_json_object_fixture(
        hass, "device_info_UE43LS003.json", DOMAIN
    )
    return rest_api


@pytest.mark.usefixtures("remote_websocket", "frame_rest_api")
async def test_art_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    art_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the art mode sensor follows the art API."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "be9554b9-c9fb-41f4-8920-22da015376a4_art_mode"

    art_api.get_artmode.return_value = "off"
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("frame_rest_api")
async def test_art_mode_off_when_tv_off(
    hass: HomeAssistant,
    remote_websocket: Mock,
    art_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the art mode sensor is off when the TV is off."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    art_api.get_artmode.reset_mock()
    remote_websocket.is_alive.return_value = False
    remote_websocket.start_listening.side_effect = OSError("Boom")
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    art_api.get_artmode.assert_not_called()


async def test_art_mode_added_when_tv_reachable_later(
    hass: HomeAssistant,
    remote_websocket: Mock,
    rest_api: Mock,
    art_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the art mode sensor is added when the TV is unreachable at startup."""
    remote_websocket.start_listening.side_effect = OSError("Boom")
    rest_api.rest_device_info.side_effect = ResponseError("Boom")
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
    assert hass.states.get(ENTITY_ID) is None

    remote_websocket.start_listening.side_effect = None
    rest_api.rest_device_info.side_effect = None
    rest_api.rest_device_info.return_value = await async_load_json_object_fixture(
        hass, "device_info_UE43LS003.json", DOMAIN
    )
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("remote_websocket")
async def test_art_mode_added_when_device_info_recovers(
    hass: HomeAssistant,
    rest_api: Mock,
    art_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the art mode sensor is added when only the REST API failed at startup."""
    rest_api.rest_device_info.side_effect = ResponseError("Boom")
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)
    assert hass.states.get(ENTITY_ID) is None

    rest_api.rest_device_info.side_effect = None
    rest_api.rest_device_info.return_value = await async_load_json_object_fixture(
        hass, "device_info_UE43LS003.json", DOMAIN
    )
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("frame_rest_api")
async def test_art_mode_off_when_tv_off_without_mac(
    hass: HomeAssistant,
    remote_websocket: Mock,
    rest_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the art mode sensor stays available when the TV can not be turned on."""
    # Without wifiMac, no MAC can be found, so the TV can not be turned on
    del rest_api.rest_device_info.return_value["device"]["wifiMac"]
    entry_data = {k: v for k, v in ENTRYDATA_WEBSOCKET.items() if k != CONF_MAC}
    entry = await setup_samsungtv_entry(hass, entry_data)
    assert CONF_MAC not in entry.data
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    remote_websocket.is_alive.return_value = False
    remote_websocket.start_listening.side_effect = OSError("Boom")
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionFailure("Boom"), id="connection_failure"),
        pytest.param(OSError("Boom"), id="os_error"),
    ],
)
@pytest.mark.usefixtures("remote_websocket", "frame_rest_api")
async def test_art_mode_unknown_on_error(
    hass: HomeAssistant, art_api: Mock, error: Exception
) -> None:
    """Test the art mode sensor is unknown when the art API fails."""
    art_api.get_artmode.side_effect = error
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_no_art_mode_without_frame_support(
    hass: HomeAssistant, art_api: Mock
) -> None:
    """Test no art mode sensor is created for TVs without Frame support."""
    await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert hass.states.get(ENTITY_ID) is None
    art_api.get_artmode.assert_not_called()


@pytest.mark.usefixtures("remote_legacy")
async def test_no_art_mode_legacy(hass: HomeAssistant) -> None:
    """Test no art mode sensor is created for legacy TVs."""
    await setup_samsungtv_entry(hass, ENTRYDATA_LEGACY)

    assert hass.states.get(ENTITY_ID) is None

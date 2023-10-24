"""Tests for the GogoGate2 component."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from ismartgate import GogoGate2Api, ISmartGateApi
from ismartgate.common import (
    DoorMode,
    DoorStatus,
    GogoGate2ActivateResponse,
    GogoGate2Door,
    GogoGate2InfoResponse,
    Network,
    Outputs,
    TransitionDoorStatus,
    Wifi,
)

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.components.gogogate2.const import (
    DEVICE_TYPE_GOGOGATE2,
    DEVICE_TYPE_ISMARTGATE,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from . import (
    _mocked_gogogate_open_door_response,
    _mocked_ismartgate_closed_door_response,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_open_close_update(gogogate2api_mock, hass: HomeAssistant) -> None:
    """Test open and close and data update."""

    def info_response(door_status: DoorStatus) -> GogoGate2InfoResponse:
        return GogoGate2InfoResponse(
            user="user1",
            gogogatename="gogogatename0",
            model="",
            apiversion="",
            remoteaccessenabled=False,
            remoteaccess="abc123.blah.blah",
            firmwareversion="",
            apicode="",
            door1=GogoGate2Door(
                door_id=1,
                permission=True,
                name="Door1",
                gate=False,
                mode=DoorMode.GARAGE,
                status=door_status,
                sensor=True,
                sensorid=None,
                camera=False,
                events=2,
                temperature=None,
                voltage=40,
            ),
            door2=GogoGate2Door(
                door_id=2,
                permission=True,
                name=None,
                gate=True,
                mode=DoorMode.GARAGE,
                status=DoorStatus.UNDEFINED,
                sensor=True,
                sensorid=None,
                camera=False,
                events=0,
                temperature=None,
                voltage=40,
            ),
            door3=GogoGate2Door(
                door_id=3,
                permission=True,
                name=None,
                gate=False,
                mode=DoorMode.GARAGE,
                status=DoorStatus.UNDEFINED,
                sensor=True,
                sensorid=None,
                camera=False,
                events=0,
                temperature=None,
                voltage=40,
            ),
            outputs=Outputs(output1=True, output2=False, output3=True),
            network=Network(ip=""),
            wifi=Wifi(SSID="", linkquality="", signal=""),
        )

    expected_attributes = {
        "device_class": "garage",
        "door_id": 1,
        "friendly_name": "Door1",
        "supported_features": CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
    }

    api = MagicMock(GogoGate2Api)
    api.async_activate.return_value = GogoGate2ActivateResponse(result=True)
    api.async_info.return_value = info_response(DoorStatus.OPENED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.OPENED,
        2: DoorStatus.OPENED,
    }
    gogogate2api_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert hass.states.get("cover.door1") is None
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPEN
    assert dict(hass.states.get("cover.door1").attributes) == expected_attributes

    api.async_info.return_value = info_response(DoorStatus.CLOSED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.CLOSED,
        2: DoorStatus.CLOSED,
    }
    await hass.services.async_call(
        COVER_DOMAIN,
        "close_cover",
        service_data={"entity_id": "cover.door1"},
    )
    api.async_get_door_statuses_from_info.return_value = {
        1: TransitionDoorStatus.CLOSING,
        2: TransitionDoorStatus.CLOSING,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSING
    api.async_close_door.assert_called_with(1)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSING

    api.async_info.return_value = info_response(DoorStatus.CLOSED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.CLOSED,
        2: DoorStatus.CLOSED,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED

    api.async_info.return_value = info_response(DoorStatus.OPENED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.OPENED,
        2: DoorStatus.OPENED,
    }
    await hass.services.async_call(
        COVER_DOMAIN,
        "open_cover",
        service_data={"entity_id": "cover.door1"},
    )
    api.async_get_door_statuses_from_info.return_value = {
        1: TransitionDoorStatus.OPENING,
        2: TransitionDoorStatus.OPENING,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPENING
    api.async_open_door.assert_called_with(1)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPENING

    api.async_info.return_value = info_response(DoorStatus.OPENED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.OPENED,
        2: DoorStatus.OPENED,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPEN

    api.async_info.return_value = info_response(DoorStatus.UNDEFINED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.UNDEFINED,
        2: DoorStatus.UNDEFINED,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_UNKNOWN

    api.async_info.return_value = info_response(DoorStatus.OPENED)
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.OPENED,
        2: DoorStatus.OPENED,
    }
    await hass.services.async_call(
        COVER_DOMAIN,
        "close_cover",
        service_data={"entity_id": "cover.door1"},
    )
    await hass.services.async_call(
        COVER_DOMAIN,
        "open_cover",
        service_data={"entity_id": "cover.door1"},
    )
    api.async_get_door_statuses_from_info.return_value = {
        1: TransitionDoorStatus.OPENING,
        2: TransitionDoorStatus.OPENING,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPENING
    api.async_open_door.assert_called_with(1)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert not hass.states.async_entity_ids(DOMAIN)


@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_availability(ismartgateapi_mock, hass: HomeAssistant) -> None:
    """Test availability."""
    closed_door_response = _mocked_ismartgate_closed_door_response()

    expected_attributes = {
        "device_class": "garage",
        "door_id": 1,
        "friendly_name": "Door1",
        "supported_features": CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
    }

    api = MagicMock(ISmartGateApi)
    api.async_info.return_value = closed_door_response
    ismartgateapi_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert hass.states.get("cover.door1") is None
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1")
    assert (
        hass.states.get("cover.door1").attributes[ATTR_DEVICE_CLASS]
        == CoverDeviceClass.GARAGE
    )
    assert (
        hass.states.get("cover.door2").attributes[ATTR_DEVICE_CLASS]
        == CoverDeviceClass.GATE
    )

    api.async_info.side_effect = Exception("Error")

    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_UNAVAILABLE

    api.async_info.side_effect = None
    api.async_info.return_value = closed_door_response
    api.async_get_door_statuses_from_info.return_value = {
        1: DoorStatus.CLOSED,
        2: DoorStatus.CLOSED,
    }
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED
    assert dict(hass.states.get("cover.door1").attributes) == expected_attributes


@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_device_info_ismartgate(
    ismartgateapi_mock, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test device info."""

    closed_door_response = _mocked_ismartgate_closed_door_response()

    api = MagicMock(ISmartGateApi)
    api.async_info.return_value = closed_door_response
    ismartgateapi_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title="mycontroller",
        unique_id="xyz",
        data={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "xyz")})
    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.name == "mycontroller"
    assert device.model == "ismartgatePRO"
    assert device.sw_version == "555"
    assert device.configuration_url == "https://abc321.blah.blah"


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_device_info_gogogate2(
    gogogate2api_mock, hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test device info."""
    closed_door_response = _mocked_gogogate_open_door_response()

    api = MagicMock(GogoGate2Api)
    api.async_info.return_value = closed_door_response
    gogogate2api_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title="mycontroller",
        unique_id="xyz",
        data={
            CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "xyz")})
    assert device
    assert device.manufacturer == MANUFACTURER
    assert device.name == "mycontroller"
    assert device.model == "gogogate2"
    assert device.sw_version == "222"
    assert device.configuration_url == "http://127.0.0.1"

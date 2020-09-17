"""Tests for the GogoGate2 component."""
from datetime import timedelta

from gogogate2_api import GogoGate2Api, ISmartGateApi
from gogogate2_api.common import (
    ApiError,
    DoorMode,
    DoorStatus,
    GogoGate2ActivateResponse,
    GogoGate2Door,
    GogoGate2InfoResponse,
    ISmartGateDoor,
    ISmartGateInfoResponse,
    Network,
    Outputs,
    Wifi,
)

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.components.gogogate2.const import (
    DEVICE_TYPE_GOGOGATE2,
    DEVICE_TYPE_ISMARTGATE,
    DOMAIN,
)
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry, async_fire_time_changed


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_import_fail(gogogate2api_mock, hass: HomeAssistant) -> None:
    """Test the failure to import."""
    api = MagicMock(spec=GogoGate2Api)
    api.info.side_effect = ApiError(22, "Error")
    gogogate2api_mock.return_value = api

    hass_config = {
        HA_DOMAIN: {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
        COVER_DOMAIN: [
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover0",
                CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
                CONF_IP_ADDRESS: "127.0.1.0",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            }
        ],
    }

    await async_process_ha_core_config(hass, hass_config[HA_DOMAIN])
    assert await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, COVER_DOMAIN, hass_config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(COVER_DOMAIN)
    assert not entity_ids


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_import(
    ismartgateapi_mock, gogogate2api_mock, hass: HomeAssistant
) -> None:
    """Test importing of file based config."""
    api0 = MagicMock(spec=GogoGate2Api)
    api0.info.return_value = GogoGate2InfoResponse(
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
            status=DoorStatus.OPENED,
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
    gogogate2api_mock.return_value = api0

    api1 = MagicMock(spec=ISmartGateApi)
    api1.info.return_value = ISmartGateInfoResponse(
        user="user1",
        ismartgatename="ismartgatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc321.blah.blah",
        firmwareversion="",
        pin=123,
        lang="en",
        newfirmware=False,
        door1=ISmartGateDoor(
            door_id=1,
            permission=True,
            name="Door1",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        door2=ISmartGateDoor(
            door_id=1,
            permission=True,
            name=None,
            gate=True,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        door3=ISmartGateDoor(
            door_id=1,
            permission=True,
            name=None,
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )
    ismartgateapi_mock.return_value = api1

    hass_config = {
        HA_DOMAIN: {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
        COVER_DOMAIN: [
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover0",
                CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
                CONF_IP_ADDRESS: "127.0.1.0",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            },
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover1",
                CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
                CONF_IP_ADDRESS: "127.0.1.1",
                CONF_USERNAME: "user1",
                CONF_PASSWORD: "password1",
            },
        ],
    }

    await async_process_ha_core_config(hass, hass_config[HA_DOMAIN])
    assert await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, COVER_DOMAIN, hass_config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(COVER_DOMAIN)
    assert entity_ids is not None
    assert len(entity_ids) == 2
    assert "cover.door1" in entity_ids
    assert "cover.door1_2" in entity_ids


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_open_close_update(gogogat2api_mock, hass: HomeAssistant) -> None:
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

    api = MagicMock(GogoGate2Api)
    api.activate.return_value = GogoGate2ActivateResponse(result=True)
    api.info.return_value = info_response(DoorStatus.OPENED)
    gogogat2api_mock.return_value = api

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

    api.info.return_value = info_response(DoorStatus.CLOSED)
    await hass.services.async_call(
        COVER_DOMAIN,
        "close_cover",
        service_data={"entity_id": "cover.door1"},
    )
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED
    api.close_door.assert_called_with(1)

    api.info.return_value = info_response(DoorStatus.OPENED)
    await hass.services.async_call(
        COVER_DOMAIN,
        "open_cover",
        service_data={"entity_id": "cover.door1"},
    )
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_OPEN
    api.open_door.assert_called_with(1)

    api.info.return_value = info_response(DoorStatus.UNDEFINED)
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert not hass.states.async_entity_ids(DOMAIN)


@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_availability(ismartgateapi_mock, hass: HomeAssistant) -> None:
    """Test availability."""
    closed_door_response = ISmartGateInfoResponse(
        user="user1",
        ismartgatename="ismartgatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        pin=123,
        lang="en",
        newfirmware=False,
        door1=ISmartGateDoor(
            door_id=1,
            permission=True,
            name="Door1",
            gate=False,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        door2=ISmartGateDoor(
            door_id=2,
            permission=True,
            name="Door2",
            gate=True,
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        door3=ISmartGateDoor(
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
            enabled=True,
            apicode="apicode0",
            customimage=False,
            voltage=40,
        ),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    api = MagicMock(ISmartGateApi)
    api.info.return_value = closed_door_response
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
        == DEVICE_CLASS_GARAGE
    )
    assert (
        hass.states.get("cover.door2").attributes[ATTR_DEVICE_CLASS]
        == DEVICE_CLASS_GATE
    )

    api.info.side_effect = Exception("Error")

    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_UNAVAILABLE

    api.info.side_effect = None
    api.info.return_value = closed_door_response
    async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED

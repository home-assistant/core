"""Tests for the GogoGate2 component."""
from gogogate2_api import GogoGate2Api
from gogogate2_api.common import (
    ActivateResponse,
    ApiError,
    Door,
    DoorMode,
    DoorStatus,
    InfoResponse,
    Network,
    Outputs,
    Wifi,
)

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from .common import ComponentFactory

from tests.async_mock import MagicMock


async def test_import_fail(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test the failure to import."""
    api = MagicMock(spec=GogoGate2Api)
    api.info.side_effect = ApiError(22, "Error")

    component_factory.api_class_mock.return_value = api

    await component_factory.configure_component(
        cover_config=[
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover0",
                CONF_IP_ADDRESS: "127.0.1.0",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            }
        ]
    )

    entity_ids = hass.states.async_entity_ids(COVER_DOMAIN)
    assert not entity_ids


async def test_import(hass: HomeAssistant, component_factory: ComponentFactory) -> None:
    """Test importing of file based config."""
    api0 = MagicMock(spec=GogoGate2Api)
    api0.info.return_value = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    api1 = MagicMock(spec=GogoGate2Api)
    api1.info.return_value = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="321bca.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    def new_api(ip_address: str, username: str, password: str) -> GogoGate2Api:
        if ip_address == "127.0.1.0":
            return api0
        if ip_address == "127.0.1.1":
            return api1
        raise Exception(f"Untested ip address {ip_address}")

    component_factory.api_class_mock.side_effect = new_api

    await component_factory.configure_component(
        cover_config=[
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover0",
                CONF_IP_ADDRESS: "127.0.1.0",
                CONF_USERNAME: "user0",
                CONF_PASSWORD: "password0",
            },
            {
                CONF_PLATFORM: "gogogate2",
                CONF_NAME: "cover1",
                CONF_IP_ADDRESS: "127.0.1.1",
                CONF_USERNAME: "user1",
                CONF_PASSWORD: "password1",
            },
        ]
    )
    entity_ids = hass.states.async_entity_ids(COVER_DOMAIN)
    assert entity_ids is not None
    assert len(entity_ids) == 2
    assert "cover.door1" in entity_ids
    assert "cover.door1_2" in entity_ids

    await component_factory.unload()


async def test_cover_update(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test cover."""
    await component_factory.configure_component()
    component_data = await component_factory.run_config_flow(
        config_data={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        }
    )

    assert hass.states.async_entity_ids(COVER_DOMAIN)

    state = hass.states.get("cover.door1")
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes["friendly_name"] == "Door1"
    assert state.attributes["supported_features"] == 3
    assert state.attributes["device_class"] == "garage"

    component_data.data_update_coordinator.api.info.return_value = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.OPENED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )
    await component_data.data_update_coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("cover.door1")
    assert state
    assert state.state == STATE_OPEN

    component_data.data_update_coordinator.api.info.return_value = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )
    await component_data.data_update_coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("cover.door1")
    assert state
    assert state.state == STATE_CLOSED


async def test_open_close(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test open and close."""
    closed_door_response = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    await component_factory.configure_component()
    assert hass.states.get("cover.door1") is None

    component_data = await component_factory.run_config_flow(
        config_data={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        }
    )

    component_data.api.activate.return_value = ActivateResponse(result=True)

    assert hass.states.get("cover.door1").state == STATE_OPEN
    await hass.services.async_call(
        COVER_DOMAIN, "close_cover", service_data={"entity_id": "cover.door1"},
    )
    await hass.async_block_till_done()
    component_data.api.close_door.assert_called_with(1)

    component_data.data_update_coordinator.api.info.return_value = closed_door_response
    await component_data.data_update_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED

    # Assert mid state changed when new status is received.
    await hass.services.async_call(
        COVER_DOMAIN, "open_cover", service_data={"entity_id": "cover.door1"},
    )
    await hass.async_block_till_done()
    component_data.api.open_door.assert_called_with(1)

    # Assert the mid state does not change when the same status is returned.
    component_data.data_update_coordinator.api.info.return_value = closed_door_response
    await component_data.data_update_coordinator.async_refresh()
    component_data.data_update_coordinator.api.info.return_value = closed_door_response
    await component_data.data_update_coordinator.async_refresh()

    await component_data.data_update_coordinator.async_refresh()
    await hass.services.async_call(
        HA_DOMAIN, "update_entity", service_data={"entity_id": "cover.door1"},
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED


async def test_availability(
    hass: HomeAssistant, component_factory: ComponentFactory
) -> None:
    """Test open and close."""
    closed_door_response = InfoResponse(
        user="user1",
        gogogatename="gogogatename0",
        model="",
        apiversion="",
        remoteaccessenabled=False,
        remoteaccess="abc123.blah.blah",
        firmwareversion="",
        apicode="",
        door1=Door(
            door_id=1,
            permission=True,
            name="Door1",
            mode=DoorMode.GARAGE,
            status=DoorStatus.CLOSED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=2,
            temperature=None,
        ),
        door2=Door(
            door_id=2,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        door3=Door(
            door_id=3,
            permission=True,
            name=None,
            mode=DoorMode.GARAGE,
            status=DoorStatus.UNDEFINED,
            sensor=True,
            sensorid=None,
            camera=False,
            events=0,
            temperature=None,
        ),
        outputs=Outputs(output1=True, output2=False, output3=True),
        network=Network(ip=""),
        wifi=Wifi(SSID="", linkquality="", signal=""),
    )

    await component_factory.configure_component()
    assert hass.states.get("cover.door1") is None

    component_data = await component_factory.run_config_flow(
        config_data={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_USERNAME: "user0",
            CONF_PASSWORD: "password0",
        }
    )
    assert hass.states.get("cover.door1").state == STATE_OPEN

    component_data.api.info.side_effect = Exception("Error")
    await component_data.data_update_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_UNAVAILABLE

    component_data.api.info.side_effect = None
    component_data.api.info.return_value = closed_door_response
    await component_data.data_update_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("cover.door1").state == STATE_CLOSED

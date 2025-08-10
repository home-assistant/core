"""The tests for the Geofency device tracker platform."""

from http import HTTPStatus
from unittest.mock import patch

from aiohttp.test_utils import TestClient
import pytest

from homeassistant import config_entries
from homeassistant.components import zone
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.geofency import CONF_MOBILE_BEACONS, DOMAIN
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.typing import ClientSessionGenerator

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811

NOT_HOME_LATITUDE = 37.239394
NOT_HOME_LONGITUDE = -115.763283

GPS_ENTER_HOME = {
    "latitude": HOME_LATITUDE,
    "longitude": HOME_LONGITUDE,
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Home",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "1",
}

GPS_EXIT_HOME = {
    "latitude": HOME_LATITUDE,
    "longitude": HOME_LONGITUDE,
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Home",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "0",
}

BEACON_ENTER_HOME = {
    "latitude": HOME_LATITUDE,
    "longitude": HOME_LONGITUDE,
    "beaconUUID": "FFEF0E83-09B2-47C8-9837-E7B563F5F556",
    "minor": "36138",
    "major": "8629",
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Home",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "1",
}

BEACON_EXIT_HOME = {
    "latitude": HOME_LATITUDE,
    "longitude": HOME_LONGITUDE,
    "beaconUUID": "FFEF0E83-09B2-47C8-9837-E7B563F5F556",
    "minor": "36138",
    "major": "8629",
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Home",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "0",
}

BEACON_ENTER_CAR = {
    "latitude": NOT_HOME_LATITUDE,
    "longitude": NOT_HOME_LONGITUDE,
    "beaconUUID": "FFEF0E83-09B2-47C8-9837-E7B563F5F556",
    "minor": "36138",
    "major": "8629",
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Car 1",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "1",
}

BEACON_EXIT_CAR = {
    "latitude": NOT_HOME_LATITUDE,
    "longitude": NOT_HOME_LONGITUDE,
    "beaconUUID": "FFEF0E83-09B2-47C8-9837-E7B563F5F556",
    "minor": "36138",
    "major": "8629",
    "device": "4A7FE356-2E9D-4264-A43F-BF80ECAEE416",
    "name": "Car 1",
    "radius": 100,
    "id": "BAAD384B-A4AE-4983-F5F5-4C2F28E68205",
    "date": "2017-08-19T10:53:53Z",
    "address": "Testing Trail 1",
    "entry": "0",
}


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf: list[Device]) -> None:
    """Mock device tracker config loading."""


@pytest.fixture
async def geofency_client(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> TestClient:
    """Geofency mock client (unauthenticated)."""

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_MOBILE_BEACONS: ["Car 1"]}}
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        return await hass_client_no_auth()


@pytest.fixture(autouse=True)
async def setup_zones(hass: HomeAssistant) -> None:
    """Set up Zone config in HA."""
    assert await async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": {
                "name": "Home",
                "latitude": HOME_LATITUDE,
                "longitude": HOME_LONGITUDE,
                "radius": 100,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def webhook_id(hass: HomeAssistant) -> str:
    """Initialize the Geofency component and get the webhook_id."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    return result["result"].data["webhook_id"]


async def test_data_validation(geofency_client: TestClient, webhook_id: str) -> None:
    """Test data validation."""
    url = f"/api/webhook/{webhook_id}"

    # No data
    req = await geofency_client.post(url)
    assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY

    missing_attributes = ["address", "device", "entry", "latitude", "longitude", "name"]

    # missing attributes
    for attribute in missing_attributes:
        copy = GPS_ENTER_HOME.copy()
        del copy[attribute]
        req = await geofency_client.post(url, data=copy)
        assert req.status == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_gps_enter_and_exit_home(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    geofency_client: TestClient,
    webhook_id: str,
) -> None:
    """Test GPS based zone enter and exit."""
    url = f"/api/webhook/{webhook_id}"

    # Enter the Home zone
    req = await geofency_client.post(url, data=GPS_ENTER_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(GPS_ENTER_HOME["device"])
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_HOME

    # Exit the Home zone
    req = await geofency_client.post(url, data=GPS_EXIT_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(GPS_EXIT_HOME["device"])
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_NOT_HOME

    # Exit the Home zone with "Send Current Position" enabled
    data = GPS_EXIT_HOME.copy()
    data["currentLatitude"] = NOT_HOME_LATITUDE
    data["currentLongitude"] = NOT_HOME_LONGITUDE

    req = await geofency_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(GPS_EXIT_HOME["device"])
    current_latitude = hass.states.get(f"device_tracker.{device_name}").attributes[
        "latitude"
    ]
    assert current_latitude == NOT_HOME_LATITUDE
    current_longitude = hass.states.get(f"device_tracker.{device_name}").attributes[
        "longitude"
    ]
    assert current_longitude == NOT_HOME_LONGITUDE

    assert len(device_registry.devices) == 1
    assert len(entity_registry.entities) == 1


async def test_beacon_enter_and_exit_home(
    hass: HomeAssistant, geofency_client: TestClient, webhook_id: str
) -> None:
    """Test iBeacon based zone enter and exit - a.k.a stationary iBeacon."""
    url = f"/api/webhook/{webhook_id}"

    # Enter the Home zone
    req = await geofency_client.post(url, data=BEACON_ENTER_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{BEACON_ENTER_HOME['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_HOME

    # Exit the Home zone
    req = await geofency_client.post(url, data=BEACON_EXIT_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{BEACON_ENTER_HOME['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_NOT_HOME


async def test_beacon_enter_and_exit_car(
    hass: HomeAssistant, geofency_client: TestClient, webhook_id: str
) -> None:
    """Test use of mobile iBeacon."""
    url = f"/api/webhook/{webhook_id}"

    # Enter the Car away from Home zone
    req = await geofency_client.post(url, data=BEACON_ENTER_CAR)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{BEACON_ENTER_CAR['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_NOT_HOME

    # Exit the Car away from Home zone
    req = await geofency_client.post(url, data=BEACON_EXIT_CAR)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{BEACON_ENTER_CAR['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_NOT_HOME

    # Enter the Car in the Home zone
    data = BEACON_ENTER_CAR.copy()
    data["latitude"] = HOME_LATITUDE
    data["longitude"] = HOME_LONGITUDE
    req = await geofency_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{data['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_HOME

    # Exit the Car in the Home zone
    req = await geofency_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(f"beacon_{data['name']}")
    state_name = hass.states.get(f"device_tracker.{device_name}").state
    assert state_name == STATE_HOME


async def test_load_unload_entry(
    hass: HomeAssistant, geofency_client: TestClient, webhook_id: str
) -> None:
    """Test that the appropriate dispatch signals are added and removed."""
    url = f"/api/webhook/{webhook_id}"

    # Enter the Home zone
    req = await geofency_client.post(url, data=GPS_ENTER_HOME)
    await hass.async_block_till_done()
    assert req.status == HTTPStatus.OK
    device_name = slugify(GPS_ENTER_HOME["device"])
    state_1 = hass.states.get(f"device_tracker.{device_name}")
    assert state_1.state == STATE_HOME

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(entry.runtime_data) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state_2 = hass.states.get(f"device_tracker.{device_name}")
    assert state_2 is not None
    assert state_1 is not state_2

    assert state_2.state == STATE_HOME
    assert state_2.attributes[ATTR_LATITUDE] == HOME_LATITUDE
    assert state_2.attributes[ATTR_LONGITUDE] == HOME_LONGITUDE

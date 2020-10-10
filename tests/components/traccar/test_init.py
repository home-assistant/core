"""The tests the for Traccar device tracker platform."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import traccar, zone
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.traccar import DOMAIN, TRACKER_UPDATE
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""


@pytest.fixture(name="client")
async def traccar_client(loop, hass, aiohttp_client):
    """Mock client for Traccar (unauthenticated)."""
    assert await async_setup_component(hass, "persistent_notification", {})

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    await hass.async_block_till_done()

    with patch("homeassistant.components.device_tracker.legacy.update_config"):
        return await aiohttp_client(hass.http.app)


@pytest.fixture(autouse=True)
async def setup_zones(loop, hass):
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


@pytest.fixture(name="webhook_id")
async def webhook_id_fixture(hass, client):
    """Initialize the Traccar component and get the webhook_id."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    return result["result"].data["webhook_id"]


async def test_missing_data(hass, client, webhook_id):
    """Test missing data."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": "1.0", "lon": "1.1", "id": "123"}

    # No data
    req = await client.post(url)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy["lat"]
    req = await client.post(url, params=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy["id"]
    req = await client.post(url, params=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, client, webhook_id):
    """Test when there is a known zone."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": str(HOME_LATITUDE), "lon": str(HOME_LONGITUDE), "id": "123"}

    # Enter the Home
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert STATE_HOME == state_name

    # Enter Home again
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert STATE_HOME == state_name

    data["lon"] = 0
    data["lat"] = 0

    # Enter Somewhere else
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert STATE_NOT_HOME == state_name

    dev_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(dev_reg.devices) == 1

    ent_reg = await hass.helpers.entity_registry.async_get_registry()
    assert len(ent_reg.entities) == 1


async def test_enter_with_attrs(hass, client, webhook_id):
    """Test when additional attributes are present."""
    url = f"/api/webhook/{webhook_id}"
    data = {
        "timestamp": 123456789,
        "lat": "1.0",
        "lon": "1.1",
        "id": "123",
        "accuracy": "10.5",
        "batt": 10,
        "speed": 100,
        "bearing": "105.32",
        "altitude": 102,
    }

    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"]))
    assert state.state == STATE_NOT_HOME
    assert state.attributes["gps_accuracy"] == 10.5
    assert state.attributes["battery_level"] == 10.0
    assert state.attributes["speed"] == 100.0
    assert state.attributes["bearing"] == 105.32
    assert state.attributes["altitude"] == 102.0

    data = {
        "lat": str(HOME_LATITUDE),
        "lon": str(HOME_LONGITUDE),
        "id": "123",
        "accuracy": 123,
        "batt": 23,
        "speed": 23,
        "bearing": 123,
        "altitude": 123,
    }

    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"]))
    assert state.state == STATE_HOME
    assert state.attributes["gps_accuracy"] == 123
    assert state.attributes["battery_level"] == 23
    assert state.attributes["speed"] == 23
    assert state.attributes["bearing"] == 123
    assert state.attributes["altitude"] == 123


async def test_two_devices(hass, client, webhook_id):
    """Test updating two different devices."""
    url = f"/api/webhook/{webhook_id}"

    data_device_1 = {"lat": "1.0", "lon": "1.1", "id": "device_1"}

    # Exit Home
    req = await client.post(url, params=data_device_1)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_1["id"]))
    assert state.state == "not_home"

    # Enter Home
    data_device_2 = dict(data_device_1)
    data_device_2["lat"] = str(HOME_LATITUDE)
    data_device_2["lon"] = str(HOME_LONGITUDE)
    data_device_2["id"] = "device_2"
    req = await client.post(url, params=data_device_2)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_2["id"]))
    assert state.state == "home"
    state = hass.states.get("{}.{}".format(DEVICE_TRACKER_DOMAIN, data_device_1["id"]))
    assert state.state == "not_home"


@pytest.mark.xfail(
    reason="The device_tracker component does not support unloading yet."
)
async def test_load_unload_entry(hass, client, webhook_id):
    """Test that the appropriate dispatch signals are added and removed."""
    url = f"/api/webhook/{webhook_id}"
    data = {"lat": str(HOME_LATITUDE), "lon": str(HOME_LONGITUDE), "id": "123"}

    # Enter the Home
    req = await client.post(url, params=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get(
        "{}.{}".format(DEVICE_TRACKER_DOMAIN, data["id"])
    ).state
    assert STATE_HOME == state_name
    assert len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE]) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await traccar.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert not hass.data[DATA_DISPATCHER][TRACKER_UPDATE]

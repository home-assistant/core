"""The tests for the Google Wifi platform."""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import homeassistant.components.google_wifi.sensor as google_wifi
from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

NAME = "foo"

MOCK_DATA = (
    '{"software": {"softwareVersion":"initial",'
    '"updateNewVersion":"initial"},'
    '"system": {"uptime":86400},'
    '"wan": {"localIpAddress":"initial", "online":true,'
    '"ipAddress":true}}'
)

MOCK_DATA_NEXT = (
    '{"software": {"softwareVersion":"next",'
    '"updateNewVersion":"0.0.0.0"},'
    '"system": {"uptime":172800},'
    '"wan": {"localIpAddress":"next", "online":false,'
    '"ipAddress":false}}'
)

MOCK_DATA_MISSING = '{"software": {},' '"system": {},' '"wan": {}}'


async def test_setup_minimum(hass, requests_mock):
    """Test setup with minimum configuration."""
    resource = f"http://{google_wifi.DEFAULT_HOST}{google_wifi.ENDPOINT}"
    requests_mock.get(resource, status_code=200)
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "google_wifi", "monitored_conditions": ["uptime"]}},
    )
    assert_setup_component(1, "sensor")


async def test_setup_get(hass, requests_mock):
    """Test setup with full configuration."""
    resource = f"http://localhost{google_wifi.ENDPOINT}"
    requests_mock.get(resource, status_code=200)
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "google_wifi",
                "host": "localhost",
                "name": "Test Wifi",
                "monitored_conditions": [
                    "current_version",
                    "new_version",
                    "uptime",
                    "last_restart",
                    "local_ip",
                    "status",
                ],
            }
        },
    )
    assert_setup_component(6, "sensor")


def setup_api(data, requests_mock):
    """Set up API with fake data."""
    resource = f"http://localhost{google_wifi.ENDPOINT}"
    now = datetime(1970, month=1, day=1)
    sensor_dict = {}
    with patch("homeassistant.util.dt.now", return_value=now):
        requests_mock.get(resource, text=data, status_code=200)
        conditions = google_wifi.MONITORED_CONDITIONS.keys()
        api = google_wifi.GoogleWifiAPI("localhost", conditions)
    for condition, cond_list in google_wifi.MONITORED_CONDITIONS.items():
        sensor_dict[condition] = {
            "sensor": google_wifi.GoogleWifiSensor(api, NAME, condition),
            "name": f"{NAME}_{condition}",
            "units": cond_list[1],
            "icon": cond_list[2],
        }
    return api, sensor_dict


def fake_delay(hass, ha_delay):
    """Fake delay to prevent update throttle."""
    hass_now = dt_util.utcnow()
    shifted_time = hass_now + timedelta(seconds=ha_delay)
    async_fire_time_changed(hass, shifted_time)


def test_name(requests_mock):
    """Test the name."""
    api, sensor_dict = setup_api(MOCK_DATA, requests_mock)
    for name in sensor_dict:
        sensor = sensor_dict[name]["sensor"]
        test_name = sensor_dict[name]["name"]
        assert test_name == sensor.name


def test_unit_of_measurement(requests_mock):
    """Test the unit of measurement."""
    api, sensor_dict = setup_api(MOCK_DATA, requests_mock)
    for name in sensor_dict:
        sensor = sensor_dict[name]["sensor"]
        assert sensor_dict[name]["units"] == sensor.unit_of_measurement


def test_icon(requests_mock):
    """Test the icon."""
    api, sensor_dict = setup_api(MOCK_DATA, requests_mock)
    for name in sensor_dict:
        sensor = sensor_dict[name]["sensor"]
        assert sensor_dict[name]["icon"] == sensor.icon


def test_state(hass, requests_mock):
    """Test the initial state."""
    api, sensor_dict = setup_api(MOCK_DATA, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in sensor_dict:
            sensor = sensor_dict[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            if name == google_wifi.ATTR_LAST_RESTART:
                assert sensor.state == "1969-12-31 00:00:00"
            elif name == google_wifi.ATTR_UPTIME:
                assert sensor.state == 1
            elif name == google_wifi.ATTR_STATUS:
                assert sensor.state == "Online"
            else:
                assert sensor.state == "initial"


def test_update_when_value_is_none(hass, requests_mock):
    """Test state gets updated to unknown when sensor returns no data."""
    api, sensor_dict = setup_api(None, requests_mock)
    for name in sensor_dict:
        sensor = sensor_dict[name]["sensor"]
        fake_delay(hass, 2)
        sensor.update()
        assert sensor.state is None


def test_update_when_value_changed(hass, requests_mock):
    """Test state gets updated when sensor returns a new status."""
    api, sensor_dict = setup_api(MOCK_DATA_NEXT, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in sensor_dict:
            sensor = sensor_dict[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            if name == google_wifi.ATTR_LAST_RESTART:
                assert sensor.state == "1969-12-30 00:00:00"
            elif name == google_wifi.ATTR_UPTIME:
                assert sensor.state == 2
            elif name == google_wifi.ATTR_STATUS:
                assert sensor.state == "Offline"
            elif name == google_wifi.ATTR_NEW_VERSION:
                assert sensor.state == "Latest"
            elif name == google_wifi.ATTR_LOCAL_IP:
                assert sensor.state == STATE_UNKNOWN
            else:
                assert sensor.state == "next"


def test_when_api_data_missing(hass, requests_mock):
    """Test state logs an error when data is missing."""
    api, sensor_dict = setup_api(MOCK_DATA_MISSING, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in sensor_dict:
            sensor = sensor_dict[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            assert sensor.state == STATE_UNKNOWN


def test_update_when_unavailable(requests_mock):
    """Test state updates when Google Wifi unavailable."""
    api, sensor_dict = setup_api(None, requests_mock)
    api.update = Mock(
        "google_wifi.GoogleWifiAPI.update",
        side_effect=update_side_effect(requests_mock),
    )
    for name in sensor_dict:
        sensor = sensor_dict[name]["sensor"]
        sensor.update()
        assert sensor.state is None


def update_side_effect(requests_mock):
    """Mock representation of update function."""
    api, sensor_dict = setup_api(MOCK_DATA, requests_mock)
    api.data = None
    api.available = False

"""The tests for the Google Wifi platform."""
from datetime import datetime, timedelta

from homeassistant import core as ha
import homeassistant.components.google_wifi.sensor as google_wifi
from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import assert_setup_component

SENSOR_DICT = {}

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


"""Tests for setting up the Google Wifi sensor platform."""


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


"""Tests for Google Wifi sensor platform."""


def setup_api(data, requests_mock):
    """Set up API with fake data."""
    resource = f"http://localhost{google_wifi.ENDPOINT}"
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        requests_mock.get(resource, text=data, status_code=200)
        conditions = google_wifi.MONITORED_CONDITIONS.keys()
        API = google_wifi.GoogleWifiAPI("localhost", conditions)
    NAME = "foo"
    for condition, cond_list in google_wifi.MONITORED_CONDITIONS.items():
        sensor = google_wifi.GoogleWifiSensor(API, NAME, condition)
        name = f"{NAME}_{condition}"
        units = cond_list[1]
        icon = cond_list[2]
        SENSOR_DICT[condition] = {
            "sensor": sensor,
            "name": name,
            "units": units,
            "icon": icon,
        }
    return API


def fake_delay(hass, ha_delay):
    """Fake delay to prevent update throttle."""
    hass_now = dt_util.utcnow()
    shifted_time = hass_now + timedelta(seconds=ha_delay)
    hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: shifted_time})


def test_name():
    """Test the name."""
    for name in SENSOR_DICT:
        sensor = SENSOR_DICT[name]["sensor"]
        test_name = SENSOR_DICT[name]["name"]
        assert test_name == sensor.name


def test_unit_of_measurement():
    """Test the unit of measurement."""
    for name in SENSOR_DICT:
        sensor = SENSOR_DICT[name]["sensor"]
        assert SENSOR_DICT[name]["units"] == sensor.unit_of_measurement


def test_icon():
    """Test the icon."""
    for name in SENSOR_DICT:
        sensor = SENSOR_DICT[name]["sensor"]
        assert SENSOR_DICT[name]["icon"] == sensor.icon


def test_state(hass, requests_mock):
    """Test the initial state."""
    setup_api(MOCK_DATA, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in SENSOR_DICT:
            sensor = SENSOR_DICT[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            if name == google_wifi.ATTR_LAST_RESTART:
                assert "1969-12-31 00:00:00" == sensor.state
            elif name == google_wifi.ATTR_UPTIME:
                assert 1 == sensor.state
            elif name == google_wifi.ATTR_STATUS:
                assert "Online" == sensor.state
            else:
                assert "initial" == sensor.state


def test_update_when_value_is_none(hass, requests_mock):
    """Test state gets updated to unknown when sensor returns no data."""
    setup_api(None, requests_mock)
    for name in SENSOR_DICT:
        sensor = SENSOR_DICT[name]["sensor"]
        fake_delay(hass, 2)
        sensor.update()
        assert sensor.state is None


def test_update_when_value_changed(hass, requests_mock):
    """Test state gets updated when sensor returns a new status."""
    setup_api(MOCK_DATA_NEXT, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in SENSOR_DICT:
            sensor = SENSOR_DICT[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            if name == google_wifi.ATTR_LAST_RESTART:
                assert "1969-12-30 00:00:00" == sensor.state
            elif name == google_wifi.ATTR_UPTIME:
                assert 2 == sensor.state
            elif name == google_wifi.ATTR_STATUS:
                assert "Offline" == sensor.state
            elif name == google_wifi.ATTR_NEW_VERSION:
                assert "Latest" == sensor.state
            elif name == google_wifi.ATTR_LOCAL_IP:
                assert STATE_UNKNOWN == sensor.state
            else:
                assert "next" == sensor.state


def test_when_api_data_missing(hass, requests_mock):
    """Test state logs an error when data is missing."""
    setup_api(MOCK_DATA_MISSING, requests_mock)
    now = datetime(1970, month=1, day=1)
    with patch("homeassistant.util.dt.now", return_value=now):
        for name in SENSOR_DICT:
            sensor = SENSOR_DICT[name]["sensor"]
            fake_delay(hass, 2)
            sensor.update()
            assert STATE_UNKNOWN == sensor.state


def test_update_when_unavailable(requests_mock):
    """Test state updates when Google Wifi unavailable."""
    API = setup_api(MOCK_DATA, requests_mock)
    API.update = Mock(
        "google_wifi.GoogleWifiAPI.update",
        side_effect=update_side_effect(requests_mock),
    )
    for name in SENSOR_DICT:
        sensor = SENSOR_DICT[name]["sensor"]
        sensor.update()
        assert sensor.state is None


def update_side_effect(requests_mock):
    """Mock representation of update function."""
    API = setup_api(MOCK_DATA, requests_mock)
    API.data = None
    API.available = False

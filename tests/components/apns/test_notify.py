"""The tests for the APNS component."""
import io
from unittest.mock import Mock, mock_open, patch

from apns2.errors import Unregistered
import pytest
import yaml

import homeassistant.components.apns.notify as apns
import homeassistant.components.notify as notify
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

CONFIG = {
    notify.DOMAIN: {
        "platform": "apns",
        "name": "test_app",
        "topic": "testapp.appname",
        "cert_file": "test_app.pem",
    }
}


@pytest.fixture(scope="module", autouse=True)
def mock_apns_notify_open():
    """Mock builtins.open for apns.notfiy."""
    with patch("homeassistant.components.apns.notify.open", mock_open(), create=True):
        yield


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def _setup_notify(hass_):
    assert isinstance(apns.load_yaml_config_file, Mock), "Found unmocked load_yaml"

    with assert_setup_component(1) as handle_config:
        assert await async_setup_component(hass_, notify.DOMAIN, CONFIG)
    assert handle_config[notify.DOMAIN]


@patch("os.path.isfile", return_value=True)
@patch("os.access", return_value=True)
async def test_apns_setup_full(mock_access, mock_isfile, hass):
    """Test setup with all data."""
    config = {
        "notify": {
            "platform": "apns",
            "name": "test_app",
            "sandbox": "True",
            "topic": "testapp.appname",
            "cert_file": "test_app.pem",
        }
    }

    with assert_setup_component(1) as handle_config:
        assert await async_setup_component(hass, notify.DOMAIN, config)
    assert handle_config[notify.DOMAIN]


async def test_apns_setup_missing_name(hass):
    """Test setup with missing name."""
    config = {
        "notify": {
            "platform": "apns",
            "topic": "testapp.appname",
            "cert_file": "test_app.pem",
        }
    }
    with assert_setup_component(0) as handle_config:
        assert await async_setup_component(hass, notify.DOMAIN, config)
    assert not handle_config[notify.DOMAIN]


async def test_apns_setup_missing_certificate(hass):
    """Test setup with missing certificate."""
    config = {
        "notify": {
            "platform": "apns",
            "name": "test_app",
            "topic": "testapp.appname",
        }
    }
    with assert_setup_component(0) as handle_config:
        assert await async_setup_component(hass, notify.DOMAIN, config)
    assert not handle_config[notify.DOMAIN]


async def test_apns_setup_missing_topic(hass):
    """Test setup with missing topic."""
    config = {
        "notify": {
            "platform": "apns",
            "name": "test_app",
            "cert_file": "test_app.pem",
        }
    }
    with assert_setup_component(0) as handle_config:
        assert await async_setup_component(hass, notify.DOMAIN, config)
    assert not handle_config[notify.DOMAIN]


@patch("homeassistant.components.apns.notify._write_device")
async def test_register_new_device(mock_write, hass):
    """Test registering a new device with a name."""
    yaml_file = {5678: {"name": "test device 2"}}

    written_devices = []

    def fake_write(_out, device):
        """Fake write_device."""
        written_devices.append(device)

    mock_write.side_effect = fake_write

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        apns.DOMAIN,
        "apns_test_app",
        {"push_id": "1234", "name": "test device"},
        blocking=True,
    )

    assert len(written_devices) == 1
    assert written_devices[0].name == "test device"


@patch("homeassistant.components.apns.notify._write_device")
async def test_register_device_without_name(mock_write, hass):
    """Test registering a without a name."""
    yaml_file = {
        1234: {"name": "test device 1", "tracking_device_id": "tracking123"},
        5678: {"name": "test device 2", "tracking_device_id": "tracking456"},
    }

    written_devices = []

    def fake_write(_out, device):
        """Fake write_device."""
        written_devices.append(device)

    mock_write.side_effect = fake_write

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        apns.DOMAIN, "apns_test_app", {"push_id": "1234"}, blocking=True
    )

    devices = {dev.push_id: dev for dev in written_devices}

    test_device = devices.get("1234")

    assert test_device is not None
    assert test_device.name is None


@patch("homeassistant.components.apns.notify._write_device")
async def test_update_existing_device(mock_write, hass):
    """Test updating an existing device."""
    yaml_file = {1234: {"name": "test device 1"}, 5678: {"name": "test device 2"}}

    written_devices = []

    def fake_write(_out, device):
        """Fake write_device."""
        written_devices.append(device)

    mock_write.side_effect = fake_write

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        apns.DOMAIN,
        "apns_test_app",
        {"push_id": "1234", "name": "updated device 1"},
        blocking=True,
    )

    devices = {dev.push_id: dev for dev in written_devices}

    test_device_1 = devices.get("1234")
    test_device_2 = devices.get("5678")

    assert test_device_1 is not None
    assert test_device_2 is not None

    assert "updated device 1" == test_device_1.name


@patch("homeassistant.components.apns.notify._write_device")
async def test_update_existing_device_with_tracking_id(mock_write, hass):
    """Test updating an existing device that has a tracking id."""
    yaml_file = {
        1234: {"name": "test device 1", "tracking_device_id": "tracking123"},
        5678: {"name": "test device 2", "tracking_device_id": "tracking456"},
    }

    written_devices = []

    def fake_write(_out, device):
        """Fake write_device."""
        written_devices.append(device)

    mock_write.side_effect = fake_write

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        apns.DOMAIN,
        "apns_test_app",
        {"push_id": "1234", "name": "updated device 1"},
        blocking=True,
    )

    devices = {dev.push_id: dev for dev in written_devices}

    test_device_1 = devices.get("1234")
    test_device_2 = devices.get("5678")

    assert test_device_1 is not None
    assert test_device_2 is not None

    assert "tracking123" == test_device_1.tracking_device_id
    assert "tracking456" == test_device_2.tracking_device_id


@patch("homeassistant.components.apns.notify.APNsClient")
async def test_send(mock_client, hass):
    """Test updating an existing device."""
    send = mock_client.return_value.send_notification

    yaml_file = {1234: {"name": "test device 1"}}

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        "notify",
        "test_app",
        {
            "message": "Hello",
            "data": {"badge": 1, "sound": "test.mp3", "category": "testing"},
        },
        blocking=True,
    )

    assert send.called
    assert 1 == len(send.mock_calls)

    target = send.mock_calls[0][1][0]
    payload = send.mock_calls[0][1][1]

    assert "1234" == target
    assert "Hello" == payload.alert
    assert 1 == payload.badge
    assert "test.mp3" == payload.sound
    assert "testing" == payload.category


@patch("homeassistant.components.apns.notify.APNsClient")
async def test_send_when_disabled(mock_client, hass):
    """Test updating an existing device."""
    send = mock_client.return_value.send_notification

    yaml_file = {1234: {"name": "test device 1", "disabled": True}}

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        "notify",
        "test_app",
        {
            "message": "Hello",
            "data": {"badge": 1, "sound": "test.mp3", "category": "testing"},
        },
        blocking=True,
    )

    assert not send.called


@patch("homeassistant.components.apns.notify.APNsClient")
async def test_send_with_state(mock_client, hass):
    """Test updating an existing device."""
    send = mock_client.return_value.send_notification

    yaml_file = {
        1234: {"name": "test device 1", "tracking_device_id": "tracking123"},
        5678: {"name": "test device 2", "tracking_device_id": "tracking456"},
    }

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ), patch("os.path.isfile", Mock(return_value=True)):
        notify_service = await hass.async_add_executor_job(
            apns.ApnsNotificationService,
            hass,
            "test_app",
            "testapp.appname",
            False,
            "test_app.pem",
        )

    notify_service.device_state_changed_listener(
        "device_tracker.tracking456",
        State("device_tracker.tracking456", None),
        State("device_tracker.tracking456", "home"),
    )

    notify_service.send_message(message="Hello", target="home")

    assert send.called
    assert 1 == len(send.mock_calls)

    target = send.mock_calls[0][1][0]
    payload = send.mock_calls[0][1][1]

    assert "5678" == target
    assert "Hello" == payload.alert


@patch("homeassistant.components.apns.notify.APNsClient")
@patch("homeassistant.components.apns.notify._write_device")
async def test_disable_when_unregistered(mock_write, mock_client, hass):
    """Test disabling a device when it is unregistered."""
    send = mock_client.return_value.send_notification
    send.side_effect = Unregistered()

    yaml_file = {
        1234: {"name": "test device 1", "tracking_device_id": "tracking123"},
        5678: {"name": "test device 2", "tracking_device_id": "tracking456"},
    }

    written_devices = []

    def fake_write(_out, device):
        """Fake write_device."""
        written_devices.append(device)

    mock_write.side_effect = fake_write

    with patch(
        "homeassistant.components.apns.notify.load_yaml_config_file",
        Mock(return_value=yaml_file),
    ):
        await _setup_notify(hass)

    assert await hass.services.async_call(
        "notify", "test_app", {"message": "Hello"}, blocking=True
    )

    devices = {dev.push_id: dev for dev in written_devices}

    test_device_1 = devices.get("1234")
    assert test_device_1 is not None
    assert test_device_1.disabled is True


async def test_write_device():
    """Test writing device."""
    out = io.StringIO()
    device = apns.ApnsDevice("123", "name", "track_id", True)

    apns._write_device(out, device)
    data = yaml.safe_load(out.getvalue())
    assert data == {
        123: {"name": "name", "tracking_device_id": "track_id", "disabled": True}
    }

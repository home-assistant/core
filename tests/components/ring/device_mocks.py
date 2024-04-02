"""Module for ring device mocks.

Creates a MagicMock for all device families, i.e. chimes, doorbells, stickup_cams and other.

Each device entry in the devices.json will have a MagicMock instead of the RingObject.

Mocks the api calls on the devices such as history() and health().
"""

from copy import deepcopy
from datetime import datetime
from time import time
from unittest.mock import MagicMock

import ring_doorbell

from homeassistant.util import dt as dt_util

from tests.common import load_json_value_fixture


def _convert_ring_created_at_to_time(fixture):
    for entry in fixture:
        dt_at = datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
        entry["created_at"] = dt_util.as_utc(dt_at)
    return fixture


DEVICES_FIXTURE = load_json_value_fixture("devices.json", "ring")
DOORBOT_HISTORY = _convert_ring_created_at_to_time(
    load_json_value_fixture("doorbot_history.json", "ring")
)
# Intercom history will be enabled in ring_doorbell 0.8.8
INTERCOM_HISTORY = _convert_ring_created_at_to_time(
    load_json_value_fixture("intercom_history.json", "ring")
)
DOORBOT_HEALTH = load_json_value_fixture("doorbot_health_attrs.json", "ring")
CHIME_HEALTH = load_json_value_fixture("chime_health_attrs.json", "ring")
DEVICE_ALERTS = load_json_value_fixture("ding_active.json", "ring")


def get_devices():
    """Return mock devices keyed by device_type and then device_id."""
    devices = {}
    for device_family, mock_generator in MOCK_GENERATORS.items():
        devices[device_family] = {
            doorbot["id"]: mock_generator(doorbot)
            for doorbot in DEVICES_FIXTURE[device_family]
        }
    return devices


def get_devices_data():
    """Return devices json used by the diagnostics module."""
    return {
        device_type: {obj["id"]: obj for obj in devices}
        for device_type, devices in DEVICES_FIXTURE.items()
    }


def get_active_alerts():
    """Return active alerts set to now."""
    dings_fixture = deepcopy(DEVICE_ALERTS)
    for ding in dings_fixture:
        ding["now"] = time()
    return dings_fixture


def _update_health_data(mock, fixture):
    """Update health data on the the device.

    Once update_health_data is called on the device it reports
    health data from the fixture. Prior to that it returns None.
    """
    mock.configure_mock(
        wifi_signal_category=fixture["device_health"].get("latest_signal_category"),
        wifi_signal_strength=fixture["device_health"].get("latest_signal_strength"),
    )


def _mocked_doorbell(device_dict):
    capabilities = ["battery", "volume", "motion_detection", "video", "history"]
    doorbell = MagicMock(spec=ring_doorbell.RingDoorBell, name="Mocked Doorbell")
    # Get the battery life if present and add to capabilities
    if battery_life := device_dict.get(
        "battery_life", device_dict.get("battery_life2")
    ):
        battery_life = min(100, battery_life)

    # Set the device attributes
    doorbell.configure_mock(**device_dict)
    # Mimic the Properties on the device
    doorbell.configure_mock(
        model="Doorbell",
        name=device_dict["description"],
        battery_life=battery_life,
        volume=device_dict["settings"].get("doorbell_volume"),
        motion_detection=device_dict["settings"].get("motion_detection_enabled"),
        wifi_signal_category=None,
    )
    doorbell.has_capability.side_effect = lambda c: c in capabilities
    # Mock the history api call
    doorbell.history.return_value = DOORBOT_HISTORY

    doorbell.configure_mock(wifi_signal_category=None, wifi_signal_strength=None)
    doorbell.update_health_data.side_effect = lambda: _update_health_data(
        doorbell, DOORBOT_HEALTH
    )
    return doorbell


def _mocked_stickupcam(device_dict):
    capabilities = [
        "battery",
        "volume",
        "motion_detection",
        "video",
        "history",
        "siren",
    ]
    stickupcam = MagicMock(spec=ring_doorbell.RingStickUpCam, name="Mocked Stickup Cam")
    if battery_life := device_dict.get(
        "battery_life", device_dict.get("battery_life2")
    ):
        battery_life = min(100, battery_life)

    stickupcam.configure_mock(**device_dict)
    stickupcam.configure_mock(
        model="Stickup Cam",
        name=device_dict["description"],
        battery_life=battery_life,
        volume=device_dict["settings"].get("doorbell_volume"),
        siren=device_dict["siren_status"].get("seconds_remaining"),
        motion_detection=device_dict["settings"].get("motion_detection_enabled"),
        wifi_signal_category=None,
    )
    if light_state := device_dict.get("led_status"):
        capabilities.append("light")
        stickupcam.configure_mock(lights=light_state)

    stickupcam.has_capability.side_effect = lambda c: c in capabilities
    stickupcam.history.return_value = DOORBOT_HISTORY

    stickupcam.configure_mock(wifi_signal_category=None, wifi_signal_strength=None)
    stickupcam.update_health_data.side_effect = lambda: _update_health_data(
        stickupcam, DOORBOT_HEALTH
    )
    return stickupcam


def _mocked_chime(device_dict):
    capabilities = ["volume"]
    chime = MagicMock(spec=ring_doorbell.RingChime, name="Mocked Chime")
    chime.configure_mock(**device_dict)
    chime.configure_mock(
        model="Chime",
        name=device_dict["description"],
        volume=device_dict["settings"].get("volume"),
    )
    chime.has_capability.side_effect = lambda c: c in capabilities

    chime.configure_mock(wifi_signal_category=None, wifi_signal_strength=None)
    chime.update_health_data.side_effect = lambda: _update_health_data(
        chime, CHIME_HEALTH
    )
    return chime


def _mocked_other(device_dict):
    capabilities = ["open", "history"]

    other = MagicMock(spec=ring_doorbell.RingOther, name="Mocked Intercom")
    other.configure_mock(**device_dict)
    other.configure_mock(
        model="Intercom",
        name=device_dict["description"],
        doorbell_volume=device_dict["settings"].get("doorbell_volume"),
        mic_volume=device_dict["settings"].get("mic_volume"),
        voice_volume=device_dict["settings"].get("voice_volume"),
    )

    other.has_capability.side_effect = lambda c: c in capabilities
    other.history.return_value = INTERCOM_HISTORY

    other.configure_mock(wifi_signal_category=None, wifi_signal_strength=None)
    other.update_health_data.side_effect = lambda: _update_health_data(
        other, DOORBOT_HEALTH
    )
    return other


# For each device_type the value is the function used to create the mock
MOCK_GENERATORS = {
    "authorized_doorbots": _mocked_doorbell,
    "chimes": _mocked_chime,
    "doorbots": _mocked_doorbell,
    "stickup_cams": _mocked_stickupcam,
    "other": _mocked_other,
}

"""Module for ring device mocks.

Creates a MagicMock for all device families, i.e. chimes, doorbells, stickup_cams and other.

Each device entry in the devices.json will have a MagicMock instead of the RingObject.

Mocks the api calls on the devices such as history() and health().
"""

from datetime import datetime
from functools import partial
from unittest.mock import AsyncMock, MagicMock

from ring_doorbell import (
    RingCapability,
    RingChime,
    RingDoorBell,
    RingOther,
    RingStickUpCam,
)
from ring_doorbell.const import DOORBELL_EXISTING_TYPE

from homeassistant.components.ring.const import DOMAIN
from homeassistant.util import dt as dt_util

from tests.common import load_json_value_fixture

DEVICES_FIXTURE = load_json_value_fixture("devices.json", DOMAIN)
DOORBOT_HISTORY = load_json_value_fixture("doorbot_history.json", DOMAIN)
INTERCOM_HISTORY = load_json_value_fixture("intercom_history.json", DOMAIN)
DOORBOT_HEALTH = load_json_value_fixture("doorbot_health_attrs.json", DOMAIN)
CHIME_HEALTH = load_json_value_fixture("chime_health_attrs.json", DOMAIN)

FRONT_DOOR_DEVICE_ID = 987654
INGRESS_DEVICE_ID = 185036587
FRONT_DEVICE_ID = 765432
INTERNAL_DEVICE_ID = 345678
DOWNSTAIRS_DEVICE_ID = 123456


def get_mock_devices():
    """Return list of mock devices keyed by device_type."""
    devices = {}
    for device_family, device_class in DEVICE_TYPES.items():
        devices[device_family] = [
            _mocked_ring_device(
                device, device_family, device_class, DEVICE_CAPABILITIES[device_class]
            )
            for device in DEVICES_FIXTURE[device_family]
        ]
    return devices


def get_devices_data():
    """Return devices raw json used by the diagnostics module."""
    return {
        device_type: {obj["id"]: obj for obj in devices}
        for device_type, devices in DEVICES_FIXTURE.items()
    }


DEVICE_TYPES = {
    "doorbots": RingDoorBell,
    "authorized_doorbots": RingDoorBell,
    "stickup_cams": RingStickUpCam,
    "chimes": RingChime,
    "other": RingOther,
}

DEVICE_CAPABILITIES = {
    RingDoorBell: [
        RingCapability.BATTERY,
        RingCapability.VOLUME,
        RingCapability.MOTION_DETECTION,
        RingCapability.VIDEO,
        RingCapability.DING,
        RingCapability.HISTORY,
    ],
    RingStickUpCam: [
        RingCapability.BATTERY,
        RingCapability.VOLUME,
        RingCapability.MOTION_DETECTION,
        RingCapability.VIDEO,
        RingCapability.HISTORY,
        RingCapability.SIREN,
        RingCapability.LIGHT,
    ],
    RingChime: [RingCapability.VOLUME],
    RingOther: [RingCapability.OPEN, RingCapability.HISTORY, RingCapability.DING],
}


def _mocked_ring_device(device_dict, device_family, device_class, capabilities):
    """Return a mocked device."""
    mock_device = MagicMock(spec=device_class, name=f"Mocked {device_family!s}")

    def has_capability(capability):
        return (
            capability in capabilities
            if isinstance(capability, RingCapability)
            else RingCapability.from_name(capability) in capabilities
        )

    def update_health_data(fixture):
        mock_device.configure_mock(
            wifi_signal_category=fixture["device_health"].get("latest_signal_category"),
            wifi_signal_strength=fixture["device_health"].get("latest_signal_strength"),
        )

    def update_history_data(fixture):
        for entry in fixture:  # Mimic the api date parsing
            if isinstance(entry["created_at"], str):
                dt_at = datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
                entry["created_at"] = dt_util.as_utc(dt_at)
        mock_device.configure_mock(last_history=fixture)  # Set last_history
        return fixture

    # Configure the device attributes
    mock_device.configure_mock(**device_dict)

    # Configure the Properties on the device
    mock_device.configure_mock(
        model=device_family,
        device_api_id=device_dict["id"],
        name=device_dict["description"],
        wifi_signal_category=None,
        wifi_signal_strength=None,
        family=device_family,
    )

    # Configure common methods
    mock_device.has_capability.side_effect = has_capability
    mock_device.async_update_health_data.side_effect = lambda: update_health_data(
        DOORBOT_HEALTH if device_family != "chimes" else CHIME_HEALTH
    )
    # Configure methods based on capability
    if has_capability(RingCapability.HISTORY):
        mock_device.configure_mock(last_history=[])
        mock_device.async_history.side_effect = lambda *_, **__: update_history_data(
            DOORBOT_HISTORY if device_family != "other" else INTERCOM_HISTORY
        )

    if has_capability(RingCapability.VIDEO):
        mock_device.async_recording_url = AsyncMock(return_value="http://dummy.url")

    if has_capability(RingCapability.MOTION_DETECTION):
        mock_device.configure_mock(
            motion_detection=device_dict["settings"].get("motion_detection_enabled"),
        )
        mock_device.async_set_motion_detection.side_effect = (
            lambda i: mock_device.configure_mock(motion_detection=i)
        )

    if has_capability(RingCapability.LIGHT):
        mock_device.configure_mock(lights=device_dict.get("led_status"))

    if has_capability(RingCapability.VOLUME):
        mock_device.configure_mock(
            volume=device_dict["settings"].get(
                "doorbell_volume", device_dict["settings"].get("volume")
            )
        )
        mock_device.async_set_volume.side_effect = lambda i: mock_device.configure_mock(
            volume=i
        )

    if has_capability(RingCapability.SIREN):
        mock_device.configure_mock(
            siren=device_dict["siren_status"].get("seconds_remaining")
        )
        mock_device.async_set_siren.side_effect = lambda i: mock_device.configure_mock(
            siren=i
        )

    if has_capability(RingCapability.BATTERY):
        mock_device.configure_mock(
            battery_life=min(
                100, device_dict.get("battery_life", device_dict.get("battery_life2"))
            )
        )

    if device_family == "doorbots":
        mock_device.configure_mock(
            existing_doorbell_type=DOORBELL_EXISTING_TYPE[
                device_dict["settings"]["chime_settings"].get("type", 2)
            ]
        )
        mock_device.configure_mock(
            existing_doorbell_type_enabled=device_dict["settings"][
                "chime_settings"
            ].get("enable", False)
        )
        mock_device.async_set_existing_doorbell_type_enabled.side_effect = (
            lambda i: mock_device.configure_mock(existing_doorbell_type_enabled=i)
        )

    if device_family == "other":
        for prop in ("doorbell_volume", "mic_volume", "voice_volume"):
            mock_device.configure_mock(
                **{
                    prop: device_dict["settings"].get(prop),
                    f"async_set_{prop}.side_effect": partial(
                        setattr, mock_device, prop
                    ),
                }
            )

    return mock_device

"""Helper functions for Hikvision integration."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET
import requests
from requests.auth import HTTPDigestAuth

if TYPE_CHECKING:
    from pyhik.hikvision import HikCamera

_LOGGER = logging.getLogger(__name__)

# Event type mapping (same as pyhik SENSOR_MAP)
SENSOR_MAP = {
    "vmd": "Motion",
    "linedetection": "Line Crossing",
    "fielddetection": "Field Detection",
    "videoloss": "Video Loss",
    "tamperdetection": "Tamper Detection",
    "shelteralarm": "Tamper Detection",
    "defocus": "Tamper Detection",
    "diskfull": "Disk Full",
    "diskerror": "Disk Error",
    "nicbroken": "Net Interface Broken",
    "ipconflict": "IP Conflict",
    "illaccess": "Illegal Access",
    "videomismatch": "Video Mismatch",
    "badvideo": "Bad Video",
    "pir": "PIR Alarm",
    "facedetection": "Face Detection",
    "scenechangedetection": "Scene Change Detection",
    "io": "I/O",
    "unattendedbaggage": "Unattended Baggage",
    "attendedbaggage": "Attended Baggage",
    "recordingfailure": "Recording Failure",
    "regionexiting": "Exiting Region",
    "regionentrance": "Entering Region",
}

# Channel name attributes to look for
CHANNEL_NAMES = [
    "dynVideoInputChannelID",
    "videoInputChannelID",
    "dynInputIOPortID",
    "inputIOPortID",
    "id",
]

# Notification methods that indicate the event is active/configured
# Expanded from pyhik's limited list of just 'center' and 'HTTP'
VALID_NOTIFICATION_METHODS = {"center", "HTTP", "record", "email", "beep"}


def get_nvr_events(
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool = False,
) -> dict[str, list[int]]:
    """Fetch events from NVR with broader notification method support.

    This function extends pyhik's event detection by also accepting
    'record', 'email', and 'beep' notification methods, which are commonly
    used on NVRs but ignored by pyhik.

    Returns a dict mapping event type names to lists of channel numbers.
    """
    protocol = "https" if ssl else "http"
    root_url = f"{protocol}://{host}:{port}"
    events: dict[str, list[int]] = {}

    session = requests.Session()
    session.auth = HTTPDigestAuth(username, password)

    urls = [
        f"{root_url}/ISAPI/Event/triggers",
        f"{root_url}/Event/triggers",
    ]

    response = None
    for url in urls:
        try:
            response = session.get(url, timeout=10)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            continue

    if response is None or response.status_code != 200:
        _LOGGER.warning("Unable to fetch event triggers from NVR")
        return events

    try:
        tree = ET.fromstring(response.text)
    except ET.ParseError as err:
        _LOGGER.error("Failed to parse event triggers XML: %s", err)
        return events

    # Find all EventTrigger elements (handle namespaces)
    namespace = ""
    root_tag = tree.tag
    if root_tag.startswith("{"):
        namespace = root_tag.split("}")[0] + "}"

    # Try different XML structures (camera vs NVR)
    event_triggers = tree.findall(f".//{namespace}EventTrigger")

    for trigger in event_triggers:
        # Get event type
        event_type_elem = trigger.find(f"{namespace}eventType")
        if event_type_elem is None or not event_type_elem.text:
            continue

        event_type = event_type_elem.text.lower()

        # Skip videoloss as pyhik uses it for watchdog
        if event_type == "videoloss":
            continue

        # Get channel number
        channel_num = 0
        for channel_name in CHANNEL_NAMES:
            channel_elem = trigger.find(f"{namespace}{channel_name}")
            if channel_elem is not None and channel_elem.text:
                try:
                    channel_num = int(channel_elem.text)
                    break
                except ValueError:
                    continue

        # Check if any valid notification method is configured
        notification_list = trigger.find(f"{namespace}EventTriggerNotificationList")
        has_valid_notification = False

        if notification_list is not None:
            for notification in notification_list:
                method_elem = notification.find(f"{namespace}notificationMethod")
                if method_elem is not None and method_elem.text:
                    if method_elem.text.lower() in VALID_NOTIFICATION_METHODS:
                        has_valid_notification = True
                        break

        if has_valid_notification:
            # Map to friendly name
            friendly_name = SENSOR_MAP.get(event_type)
            if friendly_name:
                events.setdefault(friendly_name, []).append(channel_num)

    session.close()
    return events


def inject_events_into_camera(camera: HikCamera, events: dict[str, list[int]]) -> None:
    """Inject discovered events into the pyhik camera's event_states.

    This allows the camera to track events that pyhik wouldn't normally detect.
    """
    for event_name, channels in events.items():
        for channel in channels:
            # Only add if not already present
            if event_name not in camera.event_states:
                camera.event_states[event_name] = []

            # Check if this channel is already tracked
            channel_exists = any(
                sensor[1] == channel for sensor in camera.event_states[event_name]
            )
            if not channel_exists:
                # Add the event state: [is_active, channel, count, last_update_time]
                camera.event_states[event_name].append(
                    [False, channel, 0, datetime.datetime.now()]
                )

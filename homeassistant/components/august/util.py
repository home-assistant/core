"""August util functions."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial

import aiohttp
from yalexs.activity import ACTION_DOORBELL_CALL_MISSED, Activity, ActivityType
from yalexs.doorbell import DoorbellDetail
from yalexs.lock import LockDetail
from yalexs.manager.const import ACTIVITY_UPDATE_INTERVAL

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client

from . import AugustData

TIME_TO_DECLARE_DETECTION = timedelta(seconds=ACTIVITY_UPDATE_INTERVAL.total_seconds())


@callback
def async_create_august_clientsession(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Create an aiohttp session for the august integration."""
    # Create an aiohttp session instead of using the default one since the
    # default one is likely to trigger august's WAF if another integration
    # is also using Cloudflare
    return aiohttp_client.async_create_clientsession(hass)


def retrieve_time_based_activity(
    activities: set[ActivityType], data: AugustData, detail: DoorbellDetail | LockDetail
) -> Activity | None:
    """Get the latest state of the sensor."""
    stream = data.activity_stream
    if latest := stream.get_latest_device_activity(detail.device_id, activities):
        return _activity_time_based(latest)
    return False


_RING_ACTIVITIES = {ActivityType.DOORBELL_DING}


def retrieve_ding_activity(
    data: AugustData, detail: DoorbellDetail | LockDetail
) -> Activity | None:
    """Get the ring/ding state."""
    stream = data.activity_stream
    latest = stream.get_latest_device_activity(detail.device_id, _RING_ACTIVITIES)
    if latest is None or (
        data.push_updates_connected and latest.action == ACTION_DOORBELL_CALL_MISSED
    ):
        return None
    return _activity_time_based(latest)


retrieve_doorbell_motion_activity = partial(
    retrieve_time_based_activity, {ActivityType.DOORBELL_MOTION}
)


def _activity_time_based(latest: Activity) -> Activity | None:
    """Get the latest state of the sensor."""
    start = latest.activity_start_time
    end = latest.activity_end_time + TIME_TO_DECLARE_DETECTION
    if start <= _native_datetime() <= end:
        return latest
    return None


def _native_datetime() -> datetime:
    """Return time in the format august uses without timezone."""
    return datetime.now()


def retrieve_online_state(
    data: AugustData, detail: DoorbellDetail | LockDetail
) -> bool:
    """Get the latest state of the sensor."""
    # The doorbell will go into standby mode when there is no motion
    # for a short while. It will wake by itself when needed so we need
    # to consider is available or we will not report motion or dings
    if isinstance(detail, DoorbellDetail):
        return detail.is_online or detail.is_standby
    return detail.bridge_is_online

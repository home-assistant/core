"""Consume the august activity stream."""
from functools import partial
import logging

from requests import RequestException

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utcnow

from .const import ACTIVITY_UPDATE_INTERVAL, AUGUST_DEVICE_UPDATE

_LOGGER = logging.getLogger(__name__)

ACTIVITY_STREAM_FETCH_LIMIT = 10
ACTIVITY_CATCH_UP_FETCH_LIMIT = 200


class ActivityStream:
    """August activity stream handler."""

    def __init__(self, hass, api, august_gateway, house_ids):
        """Init August activity stream object."""
        self._hass = hass
        self._august_gateway = august_gateway
        self._api = api
        self._house_ids = house_ids
        self._latest_activities_by_id_type = {}
        self._last_update_time = None
        self._abort_async_track_time_interval = None

    async def async_start(self):
        """Start fetching updates from the activity stream."""
        await self._async_update(utcnow)
        self._abort_async_track_time_interval = async_track_time_interval(
            self._hass, self._async_update, ACTIVITY_UPDATE_INTERVAL
        )

    @callback
    def async_stop(self):
        """Stop fetching updates from the activity stream."""
        if self._abort_async_track_time_interval is None:
            return
        self._abort_async_track_time_interval()

    @callback
    def async_get_latest_device_activity(self, device_id, activity_types):
        """Return latest activity that is one of the acitivty_types."""
        if device_id not in self._latest_activities_by_id_type:
            return None

        latest_device_activities = self._latest_activities_by_id_type[device_id]
        latest_activity = None

        for activity_type in activity_types:
            if activity_type in latest_device_activities:
                if (
                    latest_activity is not None
                    and latest_device_activities[activity_type].activity_start_time
                    <= latest_activity.activity_start_time
                ):
                    continue
                latest_activity = latest_device_activities[activity_type]

        return latest_activity

    async def _async_update(self, time):
        """Update the activity stream from August."""

        # This is the only place we refresh the api token
        await self._august_gateway.async_refresh_access_token_if_needed()
        await self._update_device_activities(time)

    async def _update_device_activities(self, time):
        _LOGGER.debug("Start retrieving device activities")

        limit = (
            ACTIVITY_STREAM_FETCH_LIMIT
            if self._last_update_time
            else ACTIVITY_CATCH_UP_FETCH_LIMIT
        )

        for house_id in self._house_ids:
            _LOGGER.debug("Updating device activity for house id %s", house_id)
            try:
                activities = await self._hass.async_add_executor_job(
                    partial(
                        self._api.get_house_activities,
                        self._august_gateway.access_token,
                        house_id,
                        limit=limit,
                    )
                )
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve activity for house id %s: %s",
                    house_id,
                    ex,
                )
            _LOGGER.debug(
                "Completed retrieving device activities for house id %s", house_id
            )

            updated_device_ids = self._process_newer_device_activities(activities)

            if updated_device_ids:
                for device_id in updated_device_ids:
                    _LOGGER.debug(
                        "async_dispatcher_send (from activity stream): AUGUST_DEVICE_UPDATE-%s",
                        device_id,
                    )
                    async_dispatcher_send(
                        self._hass, f"{AUGUST_DEVICE_UPDATE}-{device_id}"
                    )

        self._last_update_time = time

    def _process_newer_device_activities(self, activities):
        updated_device_ids = set()
        for activity in activities:
            self._latest_activities_by_id_type.setdefault(activity.device_id, {})

            lastest_activity = self._latest_activities_by_id_type[
                activity.device_id
            ].get(activity.activity_type)

            # Ignore activities that are older than the latest one
            if (
                lastest_activity
                and lastest_activity.activity_start_time >= activity.activity_start_time
            ):
                continue

            self._latest_activities_by_id_type[activity.device_id][
                activity.activity_type
            ] = activity

            updated_device_ids.add(activity.device_id)

        return updated_device_ids

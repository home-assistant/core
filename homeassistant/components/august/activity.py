"""Consume the august activity stream."""
import logging

from aiohttp import ClientError

from homeassistant.util.dt import utcnow

from .const import ACTIVITY_UPDATE_INTERVAL
from .subscriber import AugustSubscriberMixin

_LOGGER = logging.getLogger(__name__)

ACTIVITY_STREAM_FETCH_LIMIT = 10
ACTIVITY_CATCH_UP_FETCH_LIMIT = 1000


class ActivityStream(AugustSubscriberMixin):
    """August activity stream handler."""

    def __init__(self, hass, api, august_gateway, house_ids):
        """Init August activity stream object."""
        super().__init__(hass, ACTIVITY_UPDATE_INTERVAL)
        self._hass = hass
        self._august_gateway = august_gateway
        self._api = api
        self._house_ids = house_ids
        self._latest_activities_by_id_type = {}
        self._last_update_time = None
        self._abort_async_track_time_interval = None

    async def async_setup(self):
        """Token refresh check and catch up the activity stream."""
        await self._async_refresh(utcnow)

    def get_latest_device_activity(self, device_id, activity_types):
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

    async def _async_refresh(self, time):
        """Update the activity stream from August."""

        # This is the only place we refresh the api token
        await self._august_gateway.async_refresh_access_token_if_needed()
        await self._async_update_device_activities(time)

    async def _async_update_device_activities(self, time):
        _LOGGER.debug("Start retrieving device activities")

        limit = (
            ACTIVITY_STREAM_FETCH_LIMIT
            if self._last_update_time
            else ACTIVITY_CATCH_UP_FETCH_LIMIT
        )

        for house_id in self._house_ids:
            _LOGGER.debug("Updating device activity for house id %s", house_id)
            try:
                activities = await self._api.async_get_house_activities(
                    self._august_gateway.access_token, house_id, limit=limit
                )
            except ClientError as ex:
                _LOGGER.error(
                    "Request error trying to retrieve activity for house id %s: %s",
                    house_id,
                    ex,
                )
                # Make sure we process the next house if one of them fails
                continue

            _LOGGER.debug(
                "Completed retrieving device activities for house id %s", house_id
            )

            updated_device_ids = self._process_newer_device_activities(activities)

            if updated_device_ids:
                for device_id in updated_device_ids:
                    _LOGGER.debug(
                        "async_signal_device_id_update (from activity stream): %s",
                        device_id,
                    )
                    self.async_signal_device_id_update(device_id)

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

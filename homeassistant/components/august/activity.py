"""Consume the august activity stream."""
import asyncio
import logging

from aiohttp import ClientError

from homeassistant.core import callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later
from homeassistant.util.dt import utcnow

from .const import ACTIVITY_UPDATE_INTERVAL
from .subscriber import AugustSubscriberMixin

_LOGGER = logging.getLogger(__name__)

ACTIVITY_STREAM_FETCH_LIMIT = 10
ACTIVITY_CATCH_UP_FETCH_LIMIT = 2500


class ActivityStream(AugustSubscriberMixin):
    """August activity stream handler."""

    def __init__(self, hass, api, august_gateway, house_ids, pubnub):
        """Init August activity stream object."""
        super().__init__(hass, ACTIVITY_UPDATE_INTERVAL)
        self._hass = hass
        self._schedule_updates = {}
        self._august_gateway = august_gateway
        self._api = api
        self._house_ids = house_ids
        self._latest_activities = {}
        self._last_update_time = None
        self.pubnub = pubnub
        self._update_debounce = {}

    async def async_setup(self):
        """Token refresh check and catch up the activity stream."""
        for house_id in self._house_ids:
            self._update_debounce[house_id] = self._async_create_debouncer(house_id)

        await self._async_refresh(utcnow())

    @callback
    def _async_create_debouncer(self, house_id):
        """Create a debouncer for the house id."""

        async def _async_update_house_id():
            await self._async_update_house_id(house_id)

        return Debouncer(
            self._hass,
            _LOGGER,
            cooldown=ACTIVITY_UPDATE_INTERVAL.total_seconds(),
            immediate=True,
            function=_async_update_house_id,
        )

    @callback
    def async_stop(self):
        """Cleanup any debounces."""
        for debouncer in self._update_debounce.values():
            debouncer.async_cancel()
        for house_id, updater in self._schedule_updates.items():
            if updater is not None:
                updater()
                self._schedule_updates[house_id] = None

    def get_latest_device_activity(self, device_id, activity_types):
        """Return latest activity that is one of the acitivty_types."""
        if device_id not in self._latest_activities:
            return None

        latest_device_activities = self._latest_activities[device_id]
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
        if self.pubnub.connected:
            _LOGGER.debug("Skipping update because pubnub is connected")
            return
        await self._async_update_device_activities(time)

    async def _async_update_device_activities(self, time):
        _LOGGER.debug("Start retrieving device activities")
        await asyncio.gather(
            *(
                self._update_debounce[house_id].async_call()
                for house_id in self._house_ids
            )
        )
        self._last_update_time = time

    @callback
    def async_schedule_house_id_refresh(self, house_id):
        """Update for a house activities now and once in the future."""
        if self._schedule_updates.get(house_id):
            self._schedule_updates[house_id]()
            self._schedule_updates[house_id] = None

        async def _update_house_activities(_):
            await self._update_debounce[house_id].async_call()

        self._hass.async_create_task(self._update_debounce[house_id].async_call())
        # Schedule an update past the debounce to ensure
        # we catch the case where the lock operator is
        # not updated or the lock failed
        self._schedule_updates[house_id] = async_call_later(
            self._hass,
            ACTIVITY_UPDATE_INTERVAL.total_seconds() + 1,
            _update_house_activities,
        )

    async def _async_update_house_id(self, house_id):
        """Update device activities for a house."""
        if self._last_update_time:
            limit = ACTIVITY_STREAM_FETCH_LIMIT
        else:
            limit = ACTIVITY_CATCH_UP_FETCH_LIMIT

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
            return

        _LOGGER.debug(
            "Completed retrieving device activities for house id %s", house_id
        )

        updated_device_ids = self.async_process_newer_device_activities(activities)

        if not updated_device_ids:
            return

        for device_id in updated_device_ids:
            _LOGGER.debug(
                "async_signal_device_id_update (from activity stream): %s",
                device_id,
            )
            self.async_signal_device_id_update(device_id)

    def async_process_newer_device_activities(self, activities):
        """Process activities if they are newer than the last one."""
        updated_device_ids = set()
        for activity in activities:
            device_id = activity.device_id
            activity_type = activity.activity_type
            device_activities = self._latest_activities.setdefault(device_id, {})
            lastest_activity = device_activities.get(activity_type)

            # Ignore activities that are older than the latest one
            if (
                lastest_activity
                and lastest_activity.activity_start_time >= activity.activity_start_time
            ):
                continue

            device_activities[activity_type] = activity

            updated_device_ids.add(device_id)

        return updated_device_ids

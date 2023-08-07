"""Consume the august activity stream."""
import asyncio
from datetime import datetime
import logging

from aiohttp import ClientError
from yalexs.activity import (
    Activity,
    ActivityType,
)
from yalexs.api_async import ApiAsync
from yalexs.pubnub_async import AugustPubNub
from yalexs.util import get_latest_activity

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later
from homeassistant.util.dt import utcnow

from .const import ACTIVITY_UPDATE_INTERVAL
from .gateway import AugustGateway
from .subscriber import AugustSubscriberMixin

_LOGGER = logging.getLogger(__name__)

ACTIVITY_STREAM_FETCH_LIMIT = 10
ACTIVITY_CATCH_UP_FETCH_LIMIT = 2500

# If there is a storm of activity (ie lock, unlock, door open, door close, etc)
# we want to debounce the updates so we don't hammer the activity api too much.
ACTIVITY_DEBOUNCE_COOLDOWN = 3


@callback
def _async_cancel_future_scheduled_updates(cancels: list[CALLBACK_TYPE]) -> None:
    """Cancel future scheduled updates."""
    for cancel in cancels:
        cancel()
    cancels.clear()


class ActivityStream(AugustSubscriberMixin):
    """August activity stream handler."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ApiAsync,
        august_gateway: AugustGateway,
        house_ids: set[str],
        pubnub: AugustPubNub,
    ) -> None:
        """Init August activity stream object."""
        super().__init__(hass, ACTIVITY_UPDATE_INTERVAL)
        self._hass = hass
        self._schedule_updates: dict[str, list[CALLBACK_TYPE]] = {}
        self._august_gateway = august_gateway
        self._api = api
        self._house_ids = house_ids
        self._latest_activities: dict[str, dict[ActivityType, Activity]] = {}
        self._did_first_update = False
        self.pubnub = pubnub
        self._update_debounce: dict[str, Debouncer] = {}

    async def async_setup(self):
        """Token refresh check and catch up the activity stream."""
        self._update_debounce = {
            house_id: self._async_create_debouncer(house_id)
            for house_id in self._house_ids
        }
        await self._async_refresh(utcnow())
        self._did_first_update = True

    @callback
    def _async_create_debouncer(self, house_id):
        """Create a debouncer for the house id."""

        async def _async_update_house_id():
            await self._async_update_house_id(house_id)

        return Debouncer(
            self._hass,
            _LOGGER,
            cooldown=ACTIVITY_DEBOUNCE_COOLDOWN,
            immediate=True,
            function=_async_update_house_id,
        )

    @callback
    def async_stop(self):
        """Cleanup any debounces."""
        for debouncer in self._update_debounce.values():
            debouncer.async_cancel()
        for cancels in self._schedule_updates.values():
            _async_cancel_future_scheduled_updates(cancels)

    def get_latest_device_activity(
        self, device_id: str, activity_types: set[ActivityType]
    ) -> Activity | None:
        """Return latest activity that is one of the activity_types."""
        if not (latest_device_activities := self._latest_activities.get(device_id)):
            return None

        latest_activity: Activity | None = None

        for activity_type in activity_types:
            if activity := latest_device_activities.get(activity_type):
                if (
                    latest_activity
                    and activity.activity_start_time
                    <= latest_activity.activity_start_time
                ):
                    continue
                latest_activity = activity

        return latest_activity

    async def _async_refresh(self, time: datetime) -> None:
        """Update the activity stream from August."""
        # This is the only place we refresh the api token
        await self._august_gateway.async_refresh_access_token_if_needed()
        if self.pubnub.connected:
            _LOGGER.debug("Skipping update because pubnub is connected")
            return
        _LOGGER.debug("Start retrieving device activities")
        await asyncio.gather(
            *(debouncer.async_call() for debouncer in self._update_debounce.values())
        )

    @callback
    def async_schedule_house_id_refresh(self, house_id: str) -> None:
        """Update for a house activities now and once in the future."""
        if cancels := self._schedule_updates.get(house_id):
            _async_cancel_future_scheduled_updates(cancels)

        debouncer = self._update_debounce[house_id]

        self._hass.async_create_task(debouncer.async_call())
        # Schedule two updates past the debounce time
        # to ensure we catch the case where the activity
        # api does not update right away and we need to poll
        # it again. Sometimes the lock operator or a doorbell
        # will not show up in the activity stream right away.
        future_updates = self._schedule_updates.setdefault(house_id, [])

        async def _update_house_activities(now: datetime) -> None:
            await debouncer.async_call()

        for step in (1, 2):
            future_updates.append(
                async_call_later(
                    self._hass,
                    (step * ACTIVITY_DEBOUNCE_COOLDOWN) + 0.1,
                    _update_house_activities,
                )
            )

    async def _async_update_house_id(self, house_id: str) -> None:
        """Update device activities for a house."""
        if self._did_first_update:
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
        self._async_process_newer_device_activities(activities)

    def _async_process_newer_device_activities(
        self, activities: list[Activity]
    ) -> None:
        """Process activities if they are newer than the last one."""
        updated_device_ids = set()
        latest_activities = self._latest_activities
        for activity in activities:
            device_id = activity.device_id
            activity_type = activity.activity_type
            device_activities = latest_activities.setdefault(device_id, {})
            # Ignore activities that are older than the latest one unless it is a non
            # locking or unlocking activity with the exact same start time.
            last_activity = device_activities.get(activity_type)
            # The activity stream can have duplicate activities. So we need
            # to call get_latest_activity to figure out if if the activity
            # is actually newer than the last one.
            latest_activity = get_latest_activity(activity, last_activity)
            if latest_activity != activity:
                continue

            device_activities[activity_type] = activity
            updated_device_ids.add(device_id)

        for device_id in updated_device_ids:
            _LOGGER.debug(
                "async_signal_device_id_update (from activity stream): %s",
                device_id,
            )
            self.async_signal_device_id_update(device_id)

"""Support for Acmeda Covers."""
import asyncio
import logging
from time import monotonic

import aiopulse
import async_timeout

from homeassistant.components.cover import ATTR_POSITION, CoverDevice
from homeassistant.const import ATTR_BATTERY_LEVEL

from .const import DOMAIN
from .helpers import remove_devices

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.data["host"]]
    cur_covers = {}
    # cur_groups = {}

    # Acmeda updates all covers via a single API call.
    #
    # If we call a service to update 2 covers, we only want the API to be
    # called once.
    #
    # The throttle decorator will return right away if a call is currently
    # in progress. This means that if we are updating 2 covers, the first one
    # is in the update method, the second one will skip it and assume the
    # update went through and updates it's data, not good!
    #
    # The current mechanism will make sure that all covers will wait till
    # the update call is done before writing their data to the state machine.
    #
    # An alternative approach would be to disable automatic polling by Home
    # Assistant and take control ourselves. This works great for polling as now
    # we trigger from 1 time update an update to all entities. However it gets
    # tricky from inside async_turn_on and async_turn_off.
    #
    # If automatic polling is enabled, Home Assistant will call the entity
    # update method after it is done calling all the services. This means that
    # when we update, we know all commands have been processed. If we trigger
    # the update from inside async_turn_on, the update will not capture the
    # changes to the second entity until the next polling update because the
    # throttle decorator will prevent the call.

    progress = None
    cover_progress = set()
    group_progress = set()

    async def request_update(is_group, object_id):
        """Request an update.

        We will only make 1 request to the server for updating at a time. If a
        request is in progress, we will join the request that is in progress.

        This approach is possible because should_poll=True. That means that
        Home Assistant will ask covers for updates during a polling cycle or
        after it has called a service.

        We keep track of the covers that are waiting for the request to finish.
        When new data comes in, we'll trigger an update for all non-waiting
        covers. This covers the case where a service is called to enable 2
        covers but in the meanwhile some other covers has changed too.
        """
        nonlocal progress

        progress_set = group_progress if is_group else cover_progress
        progress_set.add(object_id)

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(update_hub())
        result = await progress
        progress = None
        cover_progress.clear()
        group_progress.clear()
        return result

    async def update_hub():
        """Update the values of the hub.

        Will update covers and, if enabled, groups from the hub.
        """
        tasks = []
        tasks.append(
            async_update_items(
                hass,
                config_entry,
                hub,
                async_add_entities,
                request_update,
                False,
                cur_covers,
                cover_progress,
            )
        )

        # tasks.append(
        #    async_update_items(
        #        hass,
        #        config_entry,
        #        hub,
        #        async_add_entities,
        #        request_update,
        #        True,
        #        cur_groups,
        #        group_progress,
        #    )
        # )

        await asyncio.wait(tasks)

    await update_hub()


async def async_update_items(
    hass,
    config_entry,
    hub,
    async_add_entities,
    request_hub_update,
    is_group,
    current,
    progress_waiting,
):
    """Update covers from the hub."""
    if not hub.authorized:
        return

    if is_group:
        api_type = "group"
        api = hub.api.rooms
    else:
        api_type = "roller"
        api = hub.api.rollers

    try:
        start = monotonic()
        with async_timeout.timeout(8):
            await hub.async_request_call(hub.api.update())
            await hub.api.event_update.wait()
    except (asyncio.TimeoutError) as err:
        _LOGGER.debug("Failed to fetch %s: %s", api_type, err)

        if not hub.available:
            return

        _LOGGER.error("Unable to reach hub %s (%s)", hub.host, err)
        hub.available = False

        for item_id, item in current.items():
            if item_id not in progress_waiting:
                item.async_schedule_update_ha_state()

        return

    finally:
        _LOGGER.debug(
            "Finished %s request in %.3f seconds", api_type, monotonic() - start
        )

    if not hub.available:
        _LOGGER.info("Reconnected to hub %s", hub.host)
        hub.available = True

    new_items = []

    for item_id, item in api.items():
        if item_id not in current:
            current[item_id] = AcmedaCover(hass, item, hub, is_group)

            new_items.append(current[item_id])
        elif item_id not in progress_waiting:
            current[item_id].async_schedule_update_ha_state()

    await remove_devices(hass, config_entry, api, current)

    if new_items:
        async_add_entities(new_items)


class AcmedaCover(CoverDevice):
    """Representation of a Acmeda cover device."""

    def __init__(
        self, hass, roller: aiopulse.Roller, hub: aiopulse.Hub, is_group=False
    ):
        """Initialize the roller."""
        self.hass = hass
        self.roller = roller
        self.hub = hub
        self.is_group = is_group
        self.roller.set_callback(self.notify_update)

    def notify_update(self):
        """Tell HA that the device has been updated."""
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the unique ID of this roller."""
        return self.roller.id

    @property
    def device_id(self):
        """Return the ID of this roller."""
        return self.unique_id

    @property
    def name(self):
        """Return the name of roller."""
        return self.roller.name

    async def close_cover(self, **kwargs):
        """Close the roller."""
        await self.roller.move_down()

    async def open_cover(self, **kwargs):
        """Open the roller."""
        await self.roller.move_up()

    async def stop_cover(self, **kwargs):
        """Stop the roller."""
        await self.roller.move_stop()

    async def set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        await self.roller.move_to(100 - kwargs[ATTR_POSITION])

    @property
    def current_cover_position(self):
        """Return the current position of the roller blind.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = 100 - self.roller.closed_percent
        return position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = self.roller.closed_percent == 100
        return is_closed

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": "Rollease Acmeda",
            # "model": self.light.productname or self.light.modelid,
            # Not yet exposed as properties in aiohue
            # "sw_version": self.light.raw["swversion"],
            "via_device": (DOMAIN, self.hub.api.id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_BATTERY_LEVEL: self.roller.battery}

    async def async_update(self):
        """Retrieve latest state."""
        pass

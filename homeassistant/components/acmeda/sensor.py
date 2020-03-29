"""Support for Acmeda Roller Blind Batteries."""
import asyncio
import logging
from time import monotonic

import aiopulse
import async_timeout

from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers import entity
from homeassistant.helpers.icon import icon_for_battery_level

from .base import AcmedaBase
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
            current[item_id] = AcmedaBattery(hass, item, hub, is_group)

            new_items.append(current[item_id])
        elif item_id not in progress_waiting:
            current[item_id].async_schedule_update_ha_state()

    await remove_devices(hass, config_entry, api, current)

    if new_items:
        async_add_entities(new_items)


class AcmedaBattery(AcmedaBase, entity.Entity):
    """Representation of a Acmeda cover device."""

    device_class = DEVICE_CLASS_BATTERY
    unit_of_measurement = UNIT_PERCENTAGE

    def __init__(
        self, hass, roller: aiopulse.Roller, hub: aiopulse.Hub, is_group=False
    ):
        """Initialize the roller."""
        super().__init__(hass, roller, hub)

    @property
    def name(self):
        """Return the name of roller."""
        return super().name + " Battery"

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self.roller.battery

    @property
    def state(self):
        """Return the state of the device."""
        return self.roller.battery

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        attr[ATTR_BATTERY_LEVEL] = self.roller.battery
        attr[ATTR_BATTERY_CHARGING] = False

        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        charging = False
        return icon_for_battery_level(
            battery_level=self.roller.battery, charging=charging
        )

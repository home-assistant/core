"""Support for dobiss covers."""
from asyncio import create_task, wait
from datetime import timedelta
import logging

from dobissapi import DOBISS_UP, DobissSwitch

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COVER_CLOSETIME,
    CONF_COVER_SET_END_POSITION,
    CONF_COVER_USE_TIMED,
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_TRAVELLING_TIME_DOWN,
    CONF_TRAVELLING_TIME_UP,
    DEFAULT_COVER_TRAVELTIME,
    DOMAIN,
    KEY_API,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobissswitch."""

    _LOGGER.debug(f"Setting up cover component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api
    # _LOGGER.warn(f"set up dobiss switch on {dobiss.host}")

    d_entities = dobiss.get_devices_by_type(DobissSwitch)
    entities = []
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        if d.buddy:
            # only add the up cover, and his buddy is down
            if d.icons_id == DOBISS_UP:
                # _LOGGER.warn(f"set up dobiss cover {d.name} and {d.buddy.name}")
                if (
                    d.name.endswith(" op")
                    or d.name.endswith(" open")
                    or (
                        config_entry.options.get(CONF_COVER_USE_TIMED) is not None
                        and not config_entry.options.get(CONF_COVER_USE_TIMED)
                    )
                ):
                    entities.append(HADobissCover(d, d.buddy, config_entry))
                else:
                    entities.append(HADobissCoverPosition(d, d.buddy, config_entry))
    if entities:
        async_add_entities(entities)


class HADobissCover(CoverEntity, RestoreEntity):
    """Dobiss Cover device."""

    should_poll = False

    supported_features = CoverEntityFeature.STOP | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, up: DobissSwitch, down: DobissSwitch, config_entry):
        """Init dobiss Switch device."""
        super().__init__()
        # do some hacky check to see which type it is --> todo: make this flexible!
        # from dobiss: if it is a shade, up and down have the same name
        # if it is a velux shade, up and down end in 'op' and 'neer'
        # if it is a velux window, up and down end in 'open' and 'dicht'
        self._device_class = CoverDeviceClass.SHADE
        self._is_velux = False
        self._name = up.name
        self._config_entry = config_entry
        if up.name.endswith(" op"):
            self._device_class = CoverDeviceClass.SHADE
            self._name = up.name[: -len(" op")]
            self._is_velux = True
        elif up.name.endswith(" open"):
            self._device_class = CoverDeviceClass.WINDOW
            self._name = up.name[: -len(" open")]
            self._is_velux = True
        self._up = up
        self._down = down
        self._last_up = False
        self._start_time = None
        self._delta = 0

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._up.object_id)},
            "name": self.name,
            "manufacturer": "dobiss",
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        prefix = "up_"
        attr = {prefix + str(key): val for key, val in self._up.attributes.items()}
        prefix = "down_"
        attr.update(
            {prefix + str(key): val for key, val in self._down.attributes.items()}
        )
        attr["last_up"] = self._last_up
        attr["delta"] = self._delta
        return attr

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._up.register_callback(self.up_callback)
        self._down.register_callback(self.down_callback)
        self._up.register_callback(self.async_write_ha_state)
        self._down.register_callback(self.async_write_ha_state)
        # todo: set _last_up with info coming from dobiss (not yet available in api now)
        # so for now, just restore the previous known last state, and hope the cover didn't move
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_up = last_state.attributes.get("last_up")
            self._delta = last_state.attributes.get("delta", 0)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._up.remove_callback(self.async_write_ha_state)
        self._down.remove_callback(self.async_write_ha_state)
        self._up.remove_callback(self.up_callback)
        self._down.remove_callback(self.down_callback)

    @property
    def name(self):
        """Return the display name of this cover."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._up.object_id}-{self._down.object_id}"

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    @property
    def is_closed(self):
        if self._down.value is None or self._up.value is None:
            return None
        if self._down.value > 0 or self._up.value > 0:
            return None
        if self._config_entry.options.get(CONF_COVER_SET_END_POSITION) or (
            self._config_entry.options.get(CONF_COVER_CLOSETIME) > 0
            and self._delta is not None
            and self._delta > self._config_entry.options.get(CONF_COVER_CLOSETIME)
        ):
            return not self._last_up
        """ stopped halfway """
        return None

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        if self._is_velux:
            return None
        return self._down.value > 0 if self._down.value else None

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        if self._is_velux:
            return None
        return self._up.value > 0 if self._up.value else None

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        if self._last_up:
            await self.async_close_cover(**kwargs)
        else:
            await self.async_open_cover(**kwargs)

    # callbacks to remember last direction
    def up_callback(self):
        if self._up.is_on and not self._down.is_on:
            self._last_up = True
            if not self._is_velux:
                self._start_time = dt_util.utcnow()
                self._delta = 0
        elif not self._up.is_on and not self._down.is_on:
            if not self._is_velux and self._start_time is not None:
                self._delta = round(
                    (dt_util.utcnow() - self._start_time).total_seconds()
                )

    def down_callback(self):
        if self._down.is_on and not self._up.is_on:
            self._last_up = False
            if not self._is_velux:
                self._start_time = dt_util.utcnow()
                self._delta = 0
        elif not self._up.is_on and not self._down.is_on:
            if not self._is_velux and self._start_time is not None:
                self._delta = round(
                    (dt_util.utcnow() - self._start_time).total_seconds()
                )

    # These methods allow HA to tell the actual device what to do. In this case, move
    # the cover to the desired position, or open and close it all the way.
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._up.turn_on()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._down.turn_on()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        if self._is_velux:
            await wait(
                [create_task(self._up.turn_on()), create_task(self._down.turn_on())]
            )
        else:
            await wait(
                [create_task(self._up.turn_off()), create_task(self._down.turn_off())]
            )


class HADobissCoverPosition(CoverEntity, RestoreEntity):
    """Dobiss Cover device."""

    should_poll = False

    supported_features = (
        CoverEntityFeature.STOP | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, up: DobissSwitch, down: DobissSwitch, config_entry):
        """Init dobiss Switch device."""
        from xknx.devices import TravelCalculator

        super().__init__()
        self._device_class = CoverDeviceClass.SHADE
        self._name = up.name
        self._config_entry = config_entry
        self._up = up
        self._down = down
        self._travel_time_down = DEFAULT_COVER_TRAVELTIME
        self._travel_time_up = DEFAULT_COVER_TRAVELTIME
        self._unsubscribe_auto_updater = None
        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)
        self._external_signal = False
        self._last_up = False
        self._last_config_check = None

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._up.object_id)},
            "name": self.name,
            "manufacturer": "dobiss",
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        prefix = "up_"
        attr = {prefix + str(key): val for key, val in self._up.attributes.items()}
        prefix = "down_"
        attr.update(
            {prefix + str(key): val for key, val in self._down.attributes.items()}
        )
        attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up
        attr["last_up"] = self._last_up
        return attr

    def check_times_changed(self):
        from datetime import datetime

        CONFIG_CHECK_INTERVAL = 30.0
        """check if we need to modify the TC."""
        if self._last_config_check is not None:
            difference = (datetime.now() - self._last_config_check).total_seconds()
            if difference < CONFIG_CHECK_INTERVAL:
                _LOGGER.debug("Skipping config check!")
                return
        _LOGGER.debug(
            "-------------------------- Doing config check! ------------------------------------"
        )
        self._last_config_check = datetime.now()
        state = self.hass.states.get(self.entity_id)
        if (
            state is not None
            and state.attributes.get(CONF_TRAVELLING_TIME_DOWN) is not None
            and state.attributes.get(CONF_TRAVELLING_TIME_UP) is not None
            and (
                state.attributes.get(CONF_TRAVELLING_TIME_DOWN)
                != self._travel_time_down
                or state.attributes.get(CONF_TRAVELLING_TIME_UP) != self._travel_time_up
                or self.tc.travel_time_down != self._travel_time_down
                or self.tc.travel_time_up != self._travel_time_up
            )
        ):
            _LOGGER.debug(
                f"check_times_changed :: up {state.attributes.get(CONF_TRAVELLING_TIME_UP)} (was {self.tc.travel_time_up}); down {state.attributes.get(CONF_TRAVELLING_TIME_DOWN)} (was {self.tc.travel_time_down})"
            )
            self._travel_time_down = state.attributes.get(CONF_TRAVELLING_TIME_DOWN)
            self._travel_time_up = state.attributes.get(CONF_TRAVELLING_TIME_UP)
            self.tc.travel_time_down = self._travel_time_down
            self.tc.travel_time_up = self._travel_time_up

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._up.register_callback(self.up_callback)
        self._down.register_callback(self.down_callback)
        self._up.register_callback(self.async_write_ha_state)
        self._down.register_callback(self.async_write_ha_state)
        """ Only cover's position matters.             """
        """ The rest is calculated from this attribute."""
        old_state = await self.async_get_last_state()
        _LOGGER.debug("async_added_to_hass :: oldState %s", old_state)
        if old_state is not None:
            if (
                self.tc is not None
                and old_state.attributes.get(CONF_TRAVELLING_TIME_DOWN) is not None
            ):
                self._travel_time_down = old_state.attributes.get(
                    CONF_TRAVELLING_TIME_DOWN
                )
            if (
                self.tc is not None
                and old_state.attributes.get(CONF_TRAVELLING_TIME_UP) is not None
            ):
                self._travel_time_up = old_state.attributes.get(CONF_TRAVELLING_TIME_UP)
            self.check_times_changed()
            if (
                self.tc is not None
                and old_state.attributes.get(ATTR_CURRENT_POSITION) is not None
            ):
                self.tc.set_position(
                    int(old_state.attributes.get(ATTR_CURRENT_POSITION))
                )
            self._last_up = old_state.attributes.get("last_up")

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._up.remove_callback(self.async_write_ha_state)
        self._down.remove_callback(self.async_write_ha_state)
        self._up.remove_callback(self.up_callback)
        self._down.remove_callback(self.down_callback)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        if self._last_up:
            await self.async_close_cover(**kwargs)
        else:
            await self.async_open_cover(**kwargs)

    @property
    def name(self):
        """Return the display name of this cover."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._up.object_id}-{self._down.object_id}"

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    @property
    def is_closed(self):
        if self.tc.is_open():
            return False
        if self.tc.is_closed():
            return True
        return None

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        from xknx.devices import TravelStatus

        return (
            self.tc.is_traveling()
            and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN
        )

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        from xknx.devices import TravelStatus

        return (
            self.tc.is_traveling()
            and self.tc.travel_direction == TravelStatus.DIRECTION_UP
        )

    @property
    def assumed_state(self):
        """Return True because covers can be stopped midway."""
        return True

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.tc.current_position()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.check_times_changed()
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            _LOGGER.debug("async_set_cover_position: %d", position)
            await self.set_position(position)

    async def async_close_cover(self, **kwargs):
        """Turn the device close."""
        _LOGGER.debug("async_close_cover")
        self.check_times_changed()
        self.tc.start_travel_down()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_CLOSE_COVER)

    async def async_open_cover(self, **kwargs):
        """Turn the device open."""
        _LOGGER.debug("async_open_cover")
        self.check_times_changed()
        self.tc.start_travel_up()
        self.start_auto_updater()
        await self._async_handle_command(SERVICE_OPEN_COVER)

    async def async_stop_cover(self, **kwargs):
        """Turn the device stop."""
        _LOGGER.debug("async_stop_cover")
        self.check_times_changed()
        if self.tc.is_traveling():
            self.tc.stop()
            self.stop_auto_updater()
        await self._async_handle_command(SERVICE_STOP_COVER)

    async def set_position(self, position):
        _LOGGER.debug("set_position")
        """Move cover to a designated position."""
        self.check_times_changed()
        current_position = self.tc.current_position()
        _LOGGER.debug(
            "set_position :: current_position: %d, new_position: %d",
            current_position,
            position,
        )
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug("set_position :: command %s", command)
            await self._async_handle_command(command)

    def start_auto_updater(self):
        """Start the autoupdater to update HASS while cover is moving."""
        _LOGGER.debug("start_auto_updater")
        if self._unsubscribe_auto_updater is None:
            _LOGGER.debug("init _unsubscribe_auto_updater")
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        _LOGGER.debug("auto_updater_hook")
        self.async_schedule_update_ha_state()
        if self.position_reached():
            _LOGGER.debug("auto_updater_hook :: position_reached")
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        _LOGGER.debug("stop_auto_updater")
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        """Return if cover has reached its final position."""
        return self.tc.position_reached()

    async def auto_stop_if_necessary(self):
        """Do auto stop if necessary."""
        if self.position_reached():
            if not self._external_signal:
                _LOGGER.debug("auto_stop_if_necessary :: calling stop command")
                await self._async_handle_command(SERVICE_STOP_COVER)
            self.tc.stop()

    async def _async_handle_command(self, command, *args):
        _LOGGER.debug("_async_handle_command :: %s", command)
        if command == "close_cover":
            self._state = False
            await self._up.turn_off()
            await self._down.turn_on()

        elif command == "open_cover":
            self._state = True
            await self._up.turn_on()
            await self._down.turn_off()

        elif command == "stop_cover":
            self._state = True
            await self._up.turn_off()
            await self._down.turn_off()
        self._external_signal = False
        # Update state of entity
        self.async_write_ha_state()

    # callbacks
    def up_callback(self):
        _LOGGER.debug("up_callback")
        if self._up.is_on and not self._down.is_on:
            self._last_up = True
        if self._up.is_on and not self._down.is_on and not self.is_opening:
            _LOGGER.debug("up_callback start when not opening")
            self._external_signal = True
            self.check_times_changed()
            self.tc.start_travel_up()
            self.start_auto_updater()
        elif not self._up.is_on and not self._down.is_on and self.tc.is_traveling():
            _LOGGER.debug("up_callback stop when travelling")
            self._external_signal = True
            self.tc.stop()
            self.stop_auto_updater()

    def down_callback(self):
        _LOGGER.debug("down_callback")
        if self._down.is_on and not self._up.is_on:
            self._last_up = False
        if self._down.is_on and not self._up.is_on and not self.is_closing:
            _LOGGER.debug("down_callback start when not closing")
            self._external_signal = True
            self.check_times_changed()
            self.tc.start_travel_down()
            self.start_auto_updater()
        elif not self._up.is_on and not self._down.is_on and self.tc.is_traveling():
            _LOGGER.debug("down_callback stop when not travelling")
            self._external_signal = True
            self.tc.stop()
            self.stop_auto_updater()

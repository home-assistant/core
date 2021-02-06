"""Support for Harmony Hub devices."""
import json
import logging

import voluptuous as vol

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .connection_state import ConnectionStateMixin
from .const import (
    ACTIVITY_POWER_OFF,
    ATTR_ACTIVITY_LIST,
    ATTR_ACTIVITY_STARTING,
    ATTR_CURRENT_ACTIVITY,
    ATTR_DEVICES_LIST,
    ATTR_LAST_ACTIVITY,
    DOMAIN,
    HARMONY_OPTIONS_UPDATE,
    PREVIOUS_ACTIVE_ACTIVITY,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_SYNC,
)
from .subscriber import HarmonyCallback

_LOGGER = logging.getLogger(__name__)

# We want to fire remote commands right away
PARALLEL_UPDATES = 0

ATTR_CHANNEL = "channel"

HARMONY_SYNC_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

HARMONY_CHANGE_CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_CHANNEL): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the Harmony config entry."""

    data = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("HarmonyData : %s", data)

    default_activity = entry.options.get(ATTR_ACTIVITY)
    delay_secs = entry.options.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

    harmony_conf_file = hass.config.path(f"harmony_{entry.unique_id}.conf")
    device = HarmonyRemote(data, default_activity, delay_secs, harmony_conf_file)
    async_add_entities([device])

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SYNC,
        HARMONY_SYNC_SCHEMA,
        "sync",
    )
    platform.async_register_entity_service(
        SERVICE_CHANGE_CHANNEL, HARMONY_CHANGE_CHANNEL_SCHEMA, "change_channel"
    )


class HarmonyRemote(ConnectionStateMixin, remote.RemoteEntity, RestoreEntity):
    """Remote representation used to control a Harmony device."""

    def __init__(self, data, activity, delay_secs, out_path):
        """Initialize HarmonyRemote class."""
        super().__init__()
        self._data = data
        self._name = data.name
        self._state = None
        self._current_activity = ACTIVITY_POWER_OFF
        self.default_activity = activity
        self._activity_starting = None
        self._is_initial_update = True
        self.delay_secs = delay_secs
        self._unique_id = data.unique_id
        self._last_activity = None
        self._config_path = out_path

    async def _async_update_options(self, data):
        """Change options when the options flow does."""
        if ATTR_DELAY_SECS in data:
            self.delay_secs = data[ATTR_DELAY_SECS]

        if ATTR_ACTIVITY in data:
            self.default_activity = data[ATTR_ACTIVITY]

    def _setup_callbacks(self):
        callbacks = {
            "connected": self.got_connected,
            "disconnected": self.got_disconnected,
            "config_updated": self.new_config,
            "activity_starting": self.new_activity,
            "activity_started": self._new_activity_finished,
        }

        self.async_on_remove(self._data.async_subscribe(HarmonyCallback(**callbacks)))

    def _new_activity_finished(self, activity_info: tuple) -> None:
        """Call for finished updated current activity."""
        self._activity_starting = None
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()

        _LOGGER.debug("%s: Harmony Hub added", self._name)

        self.async_on_remove(self._clear_disconnection_delay)
        self._setup_callbacks()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{HARMONY_OPTIONS_UPDATE}-{self.unique_id}",
                self._async_update_options,
            )
        )

        # Store Harmony HUB config, this will also update our current
        # activity
        await self.new_config()

        # Restore the last activity so we know
        # how what to turn on if nothing
        # is specified
        last_state = await self.async_get_last_state()
        if not last_state:
            return
        if ATTR_LAST_ACTIVITY not in last_state.attributes:
            return
        if self.is_on:
            return

        self._last_activity = last_state.attributes[ATTR_LAST_ACTIVITY]

    @property
    def device_info(self):
        """Return device info."""
        return self._data.device_info(DOMAIN)

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def should_poll(self):
        """Return the fact that we should not be polled."""
        return False

    @property
    def device_state_attributes(self):
        """Add platform specific attributes."""
        return {
            ATTR_ACTIVITY_STARTING: self._activity_starting,
            ATTR_CURRENT_ACTIVITY: self._current_activity,
            ATTR_ACTIVITY_LIST: self._data.activity_names,
            ATTR_DEVICES_LIST: self._data.device_names,
            ATTR_LAST_ACTIVITY: self._last_activity,
        }

    @property
    def is_on(self):
        """Return False if PowerOff is the current activity, otherwise True."""
        return self._current_activity not in [None, "PowerOff"]

    @property
    def available(self):
        """Return True if connected to Hub, otherwise False."""
        return self._data.available

    def new_activity(self, activity_info: tuple) -> None:
        """Call for updating the current activity."""
        activity_id, activity_name = activity_info
        _LOGGER.debug("%s: activity reported as: %s", self._name, activity_name)
        self._current_activity = activity_name
        if self._is_initial_update:
            self._is_initial_update = False
        else:
            self._activity_starting = activity_name
        if activity_id != -1:
            # Save the activity so we can restore
            # to that activity if none is specified
            # when turning on
            self._last_activity = activity_name
        self._state = bool(activity_id != -1)
        self.async_write_ha_state()

    async def new_config(self, _=None):
        """Call for updating the current activity."""
        _LOGGER.debug("%s: configuration has been updated", self._name)
        self.new_activity(self._data.current_activity)
        await self.hass.async_add_executor_job(self.write_config_file)

    async def async_turn_on(self, **kwargs):
        """Start an activity from the Harmony device."""
        _LOGGER.debug("%s: Turn On", self.name)

        activity = kwargs.get(ATTR_ACTIVITY, self.default_activity)

        if not activity or activity == PREVIOUS_ACTIVE_ACTIVITY:
            if self._last_activity:
                activity = self._last_activity
            else:
                all_activities = self._data.activity_names
                if all_activities:
                    activity = all_activities[0]

        if activity:
            await self._data.async_start_activity(activity)
        else:
            _LOGGER.error("%s: No activity specified with turn_on service", self.name)

    async def async_turn_off(self, **kwargs):
        """Start the PowerOff activity."""
        await self._data.async_power_off()

    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to one device."""
        _LOGGER.debug("%s: Send Command", self.name)
        device = kwargs.get(ATTR_DEVICE)
        if device is None:
            _LOGGER.error("%s: Missing required argument: device", self.name)
            return

        num_repeats = kwargs[ATTR_NUM_REPEATS]
        delay_secs = kwargs.get(ATTR_DELAY_SECS, self.delay_secs)
        hold_secs = kwargs[ATTR_HOLD_SECS]
        await self._data.async_send_command(
            command, device, num_repeats, delay_secs, hold_secs
        )

    async def change_channel(self, channel):
        """Change the channel using Harmony remote."""
        await self._data.change_channel(channel)

    async def sync(self):
        """Sync the Harmony device with the web service."""
        if await self._data.sync():
            await self.hass.async_add_executor_job(self.write_config_file)

    def write_config_file(self):
        """Write Harmony configuration file.

        This is a handy way for users to figure out the available commands for automations.
        """
        _LOGGER.debug(
            "%s: Writing hub configuration to file: %s", self.name, self._config_path
        )
        json_config = self._data.json_config
        if json_config is None:
            _LOGGER.warning("%s: No configuration received from hub", self.name)
            return

        try:
            with open(self._config_path, "w+", encoding="utf-8") as file_out:
                json.dump(json_config, file_out, sort_keys=True, indent=4)
        except OSError as exc:
            _LOGGER.error(
                "%s: Unable to write HUB configuration to %s: %s",
                self.name,
                self._config_path,
                exc,
            )

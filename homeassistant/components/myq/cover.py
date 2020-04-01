"""Support for MyQ-Enabled Garage Doors."""
import logging
import time

import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverDevice,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    KNOWN_MODELS,
    MANUFACTURER,
    MYQ_COORDINATOR,
    MYQ_DEVICE_STATE,
    MYQ_DEVICE_STATE_ONLINE,
    MYQ_DEVICE_TYPE,
    MYQ_DEVICE_TYPE_GATE,
    MYQ_GATEWAY,
    MYQ_TO_HASS,
    TRANSITION_COMPLETE_DURATION,
    TRANSITION_START_DURATION,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        # This parameter is no longer used; keeping it to avoid a breaking change in
        # a hotfix, but in a future main release, this should be removed:
        vol.Optional(CONF_TYPE): cv.string,
    },
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQDevice(coordinator, device) for device in myq.covers.values()], True
    )


class MyQDevice(CoverDevice):
    """Representation of a MyQ cover."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        self._coordinator = coordinator
        self._device = device
        self._last_action_timestamp = 0
        self._scheduled_transition_update = None

    @property
    def device_class(self):
        """Define this cover as a garage door."""
        device_type = self._device.device_json.get(MYQ_DEVICE_TYPE)
        if device_type is not None and device_type == MYQ_DEVICE_TYPE_GATE:
            return DEVICE_CLASS_GATE
        return DEVICE_CLASS_GARAGE

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self._device.name

    @property
    def available(self):
        """Return if the device is online."""
        if not self._coordinator.last_update_success:
            return False

        # Not all devices report online so assume True if its missing
        return self._device.device_json[MYQ_DEVICE_STATE].get(
            MYQ_DEVICE_STATE_ONLINE, True
        )

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSED

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OPENING

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device.device_id

    async def async_close_cover(self, **kwargs):
        """Issue close command to cover."""
        self._last_action_timestamp = time.time()
        await self._device.close()
        self._async_schedule_update_for_transition()

    async def async_open_cover(self, **kwargs):
        """Issue open command to cover."""
        self._last_action_timestamp = time.time()
        await self._device.open()
        self._async_schedule_update_for_transition()

    @callback
    def _async_schedule_update_for_transition(self):
        self.async_write_ha_state()

        # Cancel any previous updates
        if self._scheduled_transition_update:
            self._scheduled_transition_update()

        # Schedule an update for when we expect the transition
        # to be completed so the garage door or gate does not
        # seem like its closing or opening for a long time
        self._scheduled_transition_update = async_call_later(
            self.hass,
            TRANSITION_COMPLETE_DURATION,
            self._async_complete_schedule_update,
        )

    async def _async_complete_schedule_update(self, _):
        """Update status of the cover via coordinator."""
        self._scheduled_transition_update = None
        await self._coordinator.async_request_refresh()

    async def async_update(self):
        """Update status of cover."""
        await self._coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._device.firmware_version,
        }
        model = KNOWN_MODELS.get(self._device.device_id[2:4])
        if model:
            device_info["model"] = model
        if self._device.parent_device_id:
            device_info["via_device"] = (DOMAIN, self._device.parent_device_id)
        return device_info

    @callback
    def _async_consume_update(self):
        if time.time() - self._last_action_timestamp <= TRANSITION_START_DURATION:
            # If we just started a transition we need
            # to prevent a bouncy state
            return

        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._coordinator.async_add_listener(self._async_consume_update)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self._coordinator.async_remove_listener(self._async_consume_update)
        if self._scheduled_transition_update:
            self._scheduled_transition_update()

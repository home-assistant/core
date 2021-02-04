"""Support for MyQ-Enabled Garage Doors."""
import time

from pymyq.const import (
    DEVICE_STATE as MYQ_DEVICE_STATE,
    DEVICE_STATE_ONLINE as MYQ_DEVICE_STATE_ONLINE,
    DEVICE_TYPE as MYQ_DEVICE_TYPE,
    DEVICE_TYPE_GATE as MYQ_DEVICE_TYPE_GATE,
    KNOWN_MODELS,
    MANUFACTURER,
)

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPENING
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MYQ_COORDINATOR,
    MYQ_GATEWAY,
    MYQ_TO_HASS,
    TRANSITION_COMPLETE_DURATION,
    TRANSITION_START_DURATION,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mysq covers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQDevice(coordinator, device) for device in myq.covers.values()], True
    )


class MyQDevice(CoordinatorEntity, CoverEntity):
    """Representation of a MyQ cover."""

    def __init__(self, coordinator, device):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
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
        if not self.coordinator.last_update_success:
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
        await self.coordinator.async_request_refresh()

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

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_consume_update)
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._scheduled_transition_update:
            self._scheduled_transition_update()

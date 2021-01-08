"""Support for toggling Amcrest IP camera settings."""
import logging

from amcrest import AmcrestError

from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import ToggleEntity

from .const import DATA_AMCREST, DEVICES, SERVICE_UPDATE
from .helpers import log_update_error, service_signal

_LOGGER = logging.getLogger(__name__)

MOTION_DETECTION = "motion_detection"
MOTION_RECORDING = "motion_recording"
# Switch types are defined like: Name, icon
SWITCHES = {
    MOTION_DETECTION: ["Motion Detection", "mdi:run-fast"],
    MOTION_RECORDING: ["Motion Recording", "mdi:record-rec"],
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the IP Amcrest camera switch platform."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestSwitch(name, device, setting)
            for setting in discovery_info[CONF_SWITCHES]
        ],
        True,
    )


class AmcrestSwitch(ToggleEntity):
    """Representation of an Amcrest IP camera switch."""

    def __init__(self, name, device, setting):
        """Initialize the Amcrest switch."""
        self._name = "{} {}".format(name, SWITCHES[setting][0])
        self._signal_name = name
        self._api = device.api
        self._setting = setting
        self._state = False
        self._icon = SWITCHES[setting][1]
        self._unsub_dispatcher = None

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn setting on."""
        if not self.available:
            return
        try:
            if self._setting == MOTION_DETECTION:
                self._api.motion_detection = "true"
            elif self._setting == MOTION_RECORDING:
                self._api.motion_recording = "true"
        except AmcrestError as error:
            log_update_error(_LOGGER, "turn on", self.name, "switch", error)

    def turn_off(self, **kwargs):
        """Turn setting off."""
        if not self.available:
            return
        try:
            if self._setting == MOTION_DETECTION:
                self._api.motion_detection = "false"
            elif self._setting == MOTION_RECORDING:
                self._api.motion_recording = "false"
        except AmcrestError as error:
            log_update_error(_LOGGER, "turn off", self.name, "switch", error)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    def update(self):
        """Update setting state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s switch", self._name)

        try:
            if self._setting == MOTION_DETECTION:
                detection = self._api.is_motion_detector_on()
            elif self._setting == MOTION_RECORDING:
                detection = self._api.is_record_on_motion_detection()
            self._state = detection
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "switch", error)

    @property
    def icon(self):
        """Return the icon for the switch."""
        return self._icon

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to update signal."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        self._unsub_dispatcher()

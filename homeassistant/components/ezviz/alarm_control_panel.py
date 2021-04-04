"""Support for Ezviz alarm."""
import logging

from pyezviz.constants import DefenseModeType

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import SUPPORT_ALARM_ARM_AWAY
from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_AWAY, ATTR_HOME, DATA_COORDINATOR, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Ezviz alarm control panel."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    alarm = [EzvizAlarm(coordinator)]

    async_add_entities(alarm)


class EzvizAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a Ezviz alarm control panel."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._location_id = "Home"
        self._mode = STATE_ALARM_DISARMED
        self._name = "Ezviz Alarm"
        self._model = "Ezviz Alarm"

    @property
    def location(self):
        """Return the location of the Alarm."""
        return self._location_id

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the alarm."""
        return self._location_id

    @property
    def state(self):
        """Return the state of the device."""
        return self._mode

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._name)},
            "name": self._name,
            "model": self._model,
            "manufacturer": MANUFACTURER,
        }

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        _LOGGER.debug("EZVIZ Defence mode to %s", ATTR_HOME)
        service_switch = getattr(DefenseModeType, ATTR_HOME)

        self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)
        self._mode = STATE_ALARM_DISARMED

    def alarm_arm_away(self, code=None):
        """Send arm command."""
        _LOGGER.debug("EZVIZ Defence mode to %s", ATTR_AWAY)
        service_switch = getattr(DefenseModeType, ATTR_AWAY)

        self.coordinator.ezviz_client.api_set_defence_mode(service_switch.value)
        self._mode = STATE_ALARM_ARMED_AWAY

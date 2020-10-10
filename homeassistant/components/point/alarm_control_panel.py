"""Support for Minut Point."""
import logging

from homeassistant.components.alarm_control_panel import DOMAIN, AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import SUPPORT_ALARM_ARM_AWAY
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as POINT_DOMAIN, POINT_DISCOVERY_NEW, SIGNAL_WEBHOOK

_LOGGER = logging.getLogger(__name__)


EVENT_MAP = {
    "off": STATE_ALARM_DISARMED,
    "alarm_silenced": STATE_ALARM_DISARMED,
    "alarm_grace_period_expired": STATE_ALARM_TRIGGERED,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Point's alarm_control_panel based on a config entry."""

    async def async_discover_home(home_id):
        """Discover and add a discovered home."""
        client = hass.data[POINT_DOMAIN][config_entry.entry_id]
        async_add_entities([MinutPointAlarmControl(client, home_id)], True)

    async_dispatcher_connect(
        hass, POINT_DISCOVERY_NEW.format(DOMAIN, POINT_DOMAIN), async_discover_home
    )


class MinutPointAlarmControl(AlarmControlPanelEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, point_client, home_id):
        """Initialize the entity."""
        self._client = point_client
        self._home_id = home_id
        self._async_unsub_hook_dispatcher_connect = None
        self._changed_by = None

    async def async_added_to_hass(self):
        """Call when entity is added to HOme Assistant."""
        await super().async_added_to_hass()
        self._async_unsub_hook_dispatcher_connect = async_dispatcher_connect(
            self.hass, SIGNAL_WEBHOOK, self._webhook_event
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        await super().async_will_remove_from_hass()
        if self._async_unsub_hook_dispatcher_connect:
            self._async_unsub_hook_dispatcher_connect()

    @callback
    def _webhook_event(self, data, webhook):
        """Process new event from the webhook."""
        _type = data.get("event", {}).get("type")
        _device_id = data.get("event", {}).get("device_id")
        _changed_by = data.get("event", {}).get("user_id")
        if (
            _device_id not in self._home["devices"] and _type not in EVENT_MAP
        ) and _type != "alarm_silenced":  # alarm_silenced does not have device_id
            return
        _LOGGER.debug("Received webhook: %s", _type)
        self._home["alarm_status"] = _type
        self._changed_by = _changed_by
        self.async_write_ha_state()

    @property
    def _home(self):
        """Return the home object."""
        return self._client.homes[self._home_id]

    @property
    def name(self):
        """Return name of the device."""
        return self._home["name"]

    @property
    def state(self):
        """Return state of the device."""
        return EVENT_MAP.get(self._home["alarm_status"], STATE_ALARM_ARMED_AWAY)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY

    @property
    def changed_by(self):
        """Return the user the last change was triggered by."""
        return self._changed_by

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        status = self._client.alarm_disarm(self._home_id)
        if status:
            self._home["alarm_status"] = "off"

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        status = self._client.alarm_arm(self._home_id)
        if status:
            self._home["alarm_status"] = "on"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"point.{self._home_id}"

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(POINT_DOMAIN, self._home_id)},
            "name": self.name,
            "manufacturer": "Minut",
        }

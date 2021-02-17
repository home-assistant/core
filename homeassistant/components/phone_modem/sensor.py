"""A sensor for incoming calls using a USB modem that supports caller ID."""
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_KEY_API,
    DOMAIN,
    ICON,
    SERVICE_HANGUP_CALL,
    SERVICE_REJECT_CALL,
    STATE_CALLERID,
    STATE_RING,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Phone Modem sensor."""
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    api = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
    sensor = [
        ModemCalleridSensor(
            hass,
            api,
            name,
            port,
            entry.entry_id,
        )
    ]
    async_add_entities(sensor, True)

    def hangup_call(call) -> None:
        """Accept Incoming Call."""
        api.hang_up()

    def reject_call(call) -> None:
        """Reject Incoming Call."""
        api.reject_call()

    hangup_call_schema = cv.make_entity_service_schema(
        {vol.Optional(SERVICE_HANGUP_CALL, default=True): cv.boolean}
    )

    reject_call_schema = cv.make_entity_service_schema(
        {vol.Optional(SERVICE_REJECT_CALL, default=True): cv.boolean}
    )

    hass.services.async_register(
        DOMAIN, SERVICE_HANGUP_CALL, hangup_call, hangup_call_schema
    )

    hass.services.async_register(
        DOMAIN, SERVICE_REJECT_CALL, reject_call, reject_call_schema
    )


class ModemCalleridSensor(Entity):
    """Implementation of USB modem caller ID sensor."""

    def __init__(self, hass, api, name, port, server_unique_id):
        """Initialize the sensor."""
        self._attributes = {"cid_time": 0, "cid_number": "", "cid_name": ""}
        self._device_class = None
        self.port = port
        self.api = api
        self._state = STATE_IDLE
        self._name = name
        self._server_unique_id = server_unique_id
        api.registercallback(self._incomingcallcallback)

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._name}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _incomingcallcallback(self, newstate):
        """Handle new states."""
        if newstate == self.api.STATE_RING:
            if self.state == self.api.STATE_IDLE:
                att = {
                    "cid_time": self.api.get_cidtime,
                    "cid_number": "",
                    "cid_name": "",
                }
                self.set_attributes(att)
            self._state = STATE_RING
            self.schedule_update_ha_state()
        elif newstate == self.api.STATE_CALLERID:
            att = {
                "cid_time": self.api.get_cidtime,
                "cid_number": self.api.get_cidnumber,
                "cid_name": self.api.get_cidname,
            }
            self.set_attributes(att)
            self._state = STATE_CALLERID
            self.schedule_update_ha_state()
        elif newstate == self.api.STATE_IDLE:
            self._state = STATE_IDLE
            self.schedule_update_ha_state()


def setup(hass):
    """Shutdown modem with Home Assistant restart."""
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_modem)


def _stop_modem(self, event):
    """HA is shutting down, close modem port."""
    if self.api:
        self.api.close()
        self.api = None

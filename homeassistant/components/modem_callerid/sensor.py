"""A sensor for incoming calls using a USB modem that supports caller ID."""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    DATA_KEY_API,
    DEFAULT_DEVICE,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SERVICE_REJECT_CALL,
    STATE_CALLERID,
    STATE_RING,
)

PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
            }
        )
    )
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Modem Caller ID sensor."""
    api = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
    async_add_entities(
        [
            ModemCalleridSensor(
                api,
                entry.data.get(CONF_NAME),
                entry.data[CONF_DEVICE],
                entry.entry_id,
            )
        ],
        True,
    )

    @callback
    async def _async_on_hass_stop(self, _):
        """HA is shutting down, close modem port."""
        if self.api:
            self.api.close()
            self.api = None

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(SERVICE_REJECT_CALL, {}, "reject_call")


class ModemCalleridSensor(SensorEntity):
    """Implementation of USB modem caller ID sensor."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(self, api, name, device, server_unique_id):
        """Initialize the sensor."""
        self._attr_extra_state_attributes = {
            "cid_time": 0,
            "cid_number": "",
            "cid_name": "",
        }
        self.device = device
        self.api = api
        self._attr_name = name
        self._attr_server_unique_id = f"{server_unique_id}_modem"

    async def async_added_to_hass(self):
        """Call when the modem sensor is added to Home Assistant."""
        self.api.registercallback(self._async_incoming_call)
        await super().async_added_to_hass()

    @callback
    def _async_incoming_call(self, new_state):
        """Handle new states."""
        if new_state == self.api.STATE_RING:
            if self.state == self.api.STATE_IDLE:
                self._attr_extra_state_attributes = {
                    "cid_time": self.api.get_cidtime,
                    "cid_number": "",
                    "cid_name": "",
                }
            self._attr_state = STATE_RING
            self.async_schedule_update_ha_state()
        elif new_state == self.api.STATE_CALLERID:
            self._attr_extra_state_attributes = {
                "cid_time": self.api.get_cidtime,
                "cid_number": self.api.get_cidnumber,
                "cid_name": self.api.get_cidname,
            }
            self._attr_state = STATE_CALLERID
            self.async_schedule_update_ha_state()
        elif new_state == self.api.STATE_IDLE:
            self._attr_state = STATE_IDLE
            self.async_schedule_update_ha_state()

    async def reject_call(self) -> None:
        """Reject Incoming Call."""
        await self.api.reject_call(self.device)

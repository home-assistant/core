"""A sensor for incoming calls using a USB modem that supports caller ID."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_IDLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CID,
    DATA_KEY_API,
    DEFAULT_DEVICE,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SERVICE_REJECT_CALL,
    STATE_CALLERID,
    STATE_RING,
)

# Deprecated in Home Assistant 2021.8
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Modem Caller ID component."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    _LOGGER.warning(
        "Loading Modem_callerid via platform setup is deprecated; Please remove it from your configuration"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Modem Caller ID sensor."""
    api = hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]
    async_add_entities(
        [
            ModemCalleridSensor(
                api,
                DEFAULT_NAME,
                entry.data[CONF_DEVICE],
                entry.entry_id,
            )
        ]
    )

    @callback
    async def _async_on_hass_stop(self):
        """HA is shutting down, close modem port."""
        if hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]:
            await hass.data[DOMAIN][entry.entry_id][DATA_KEY_API].close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_REJECT_CALL, {}, "reject_call")


class ModemCalleridSensor(SensorEntity):
    """Implementation of USB modem caller ID sensor."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(self, api, name, device, server_unique_id):
        """Initialize the sensor."""
        self.device = device
        self.api = api
        self._attr_name = name
        self._attr_unique_id = f"{server_unique_id}_modem"
        self._attr_state = STATE_IDLE
        self._attr_extra_state_attributes = {
            CID.CID_TIME: 0,
            CID.CID_NUMBER: "",
            CID.CID_NAME: "",
        }

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
                    CID.CID_TIME: self.api.get_cidtime,
                    CID.CID_NUMBER: "",
                    CID.CID_NAME: "",
                }
            self._attr_state = STATE_RING
            self.async_schedule_update_ha_state()
        elif new_state == self.api.STATE_CALLERID:
            self._attr_extra_state_attributes = {
                CID.CID_TIME: self.api.get_cidtime,
                CID.CID_NUMBER: self.api.get_cidnumber,
                CID.CID_NAME: self.api.get_cidname,
            }
            self._attr_state = STATE_CALLERID
            self.async_schedule_update_ha_state()
        elif new_state == self.api.STATE_IDLE:
            self._attr_state = STATE_IDLE
            self.async_schedule_update_ha_state()

    async def reject_call(self) -> None:
        """Reject Incoming Call."""
        await self.api.reject_call(self.device)

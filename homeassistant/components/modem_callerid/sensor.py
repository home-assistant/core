"""A sensor for incoming calls using a USB modem that supports caller ID."""
from __future__ import annotations

from phone_modem import DEFAULT_PORT, PhoneModem
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

from .const import CID, DATA_KEY_API, DEFAULT_NAME, DOMAIN, ICON, SERVICE_REJECT_CALL

# Deprecated in Home Assistant 2021.10
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DEVICE, default=DEFAULT_PORT): cv.string,
            }
        )
    )
)


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
                entry.title,
                entry.data[CONF_DEVICE],
                entry.entry_id,
            )
        ]
    )

    async def _async_on_hass_stop(self) -> None:
        """HA is shutting down, close modem port."""
        if hass.data[DOMAIN][entry.entry_id][DATA_KEY_API]:
            await hass.data[DOMAIN][entry.entry_id][DATA_KEY_API].close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(SERVICE_REJECT_CALL, {}, "async_reject_call")


class ModemCalleridSensor(SensorEntity):
    """Implementation of USB modem caller ID sensor."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(
        self, api: PhoneModem, name: str, device: str, server_unique_id: str
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self.api = api
        self._attr_name = name
        self._attr_unique_id = server_unique_id
        self._attr_native_value = STATE_IDLE
        self._attr_extra_state_attributes = {
            CID.CID_TIME: 0,
            CID.CID_NUMBER: "",
            CID.CID_NAME: "",
        }

    async def async_added_to_hass(self) -> None:
        """Call when the modem sensor is added to Home Assistant."""
        self.api.registercallback(self._async_incoming_call)
        await super().async_added_to_hass()

    @callback
    def _async_incoming_call(self, new_state) -> None:
        """Handle new states."""
        if new_state == PhoneModem.STATE_RING:
            if self.native_value == PhoneModem.STATE_IDLE:
                self._attr_extra_state_attributes = {
                    CID.CID_NUMBER: "",
                    CID.CID_NAME: "",
                }
        elif new_state == PhoneModem.STATE_CALLERID:
            self._attr_extra_state_attributes = {
                CID.CID_NUMBER: self.api.cid_number,
                CID.CID_NAME: self.api.cid_name,
            }
        self._attr_extra_state_attributes[CID.CID_TIME] = self.api.cid_time
        self._attr_native_value = self.api.state
        self.async_write_ha_state()

    async def async_reject_call(self) -> None:
        """Reject Incoming Call."""
        await self.api.reject_call(self.device)

"""Switches for the Elexa Guardian integration."""
from aioguardian.errors import GuardianError

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback

from . import Guardian, GuardianEntity
from .const import (
    DATA_CLIENT,
    DATA_DIAGNOSTICS,
    DATA_VALVE_STATUS,
    DATA_WIFI_STATUS,
    DOMAIN,
    LOGGER,
)

ATTR_AP_CLIENTS = "ap_clients"
ATTR_AP_ENABLED = "ap_enabled"
ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_RSSI = "rssi"
ATTR_STATION_CONNECTED = "station_connected"
ATTR_TRAVEL_COUNT = "travel_count"
ATTR_UPTIME = "uptime"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine switches based on a config entry."""
    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities([GuardianSwitch(guardian)], True)


class GuardianSwitch(GuardianEntity, SwitchDevice):
    """Define a switch to open/close the Guardian valve."""

    def __init__(self, guardian: Guardian):
        """Initialize."""
        super().__init__(guardian)

        self._is_on = True

    @property
    def is_on(self):
        """Return True if the valve is open."""
        return self._is_on

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.valve_close()
        except GuardianError as err:
            LOGGER.error("Error while closing the valve: %s", err)
            return

        self._is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.valve_open()
        except GuardianError as err:
            LOGGER.error("Error while opening the valve: %s", err)
            return

        self._is_on = True

    @callback
    def update_from_latest_data(self):
        """Update the entity."""
        self._is_on = self._guardian.data[DATA_VALVE_STATUS]["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attrs.update(
            {
                ATTR_AP_CLIENTS: self._guardian.data[DATA_WIFI_STATUS]["ap_clients"],
                ATTR_AP_ENABLED: self._guardian.data[DATA_WIFI_STATUS]["ap_enabled"],
                ATTR_AVG_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "average_current"
                ],
                ATTR_INST_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current_ddt"
                ],
                ATTR_RSSI: self._guardian.data[DATA_WIFI_STATUS]["rssi"],
                ATTR_STATION_CONNECTED: self._guardian.data[DATA_WIFI_STATUS][
                    "station_connected"
                ],
                ATTR_TRAVEL_COUNT: self._guardian.data[DATA_VALVE_STATUS][
                    "travel_count"
                ],
                ATTR_UPTIME: self._guardian.data[DATA_DIAGNOSTICS]["uptime"],
            }
        )

"""Switches for the Elexa Guardian integration."""
from aioguardian.errors import GuardianError

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import Guardian, GuardianEntity
from .const import DATA_CLIENT, DATA_VALVE_STATUS, DOMAIN, LOGGER, SWITCH_KIND_VALVE

ATTR_AVG_CURRENT = "average_current"
ATTR_INST_CURRENT = "instantaneous_current"
ATTR_INST_CURRENT_DDT = "instantaneous_current_ddt"
ATTR_TRAVEL_COUNT = "travel_count"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Guardian switches based on a config entry."""
    guardian = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities([GuardianSwitch(guardian)], True)


class GuardianSwitch(GuardianEntity, SwitchEntity):
    """Define a switch to open/close the Guardian valve."""

    def __init__(self, guardian: Guardian):
        """Initialize."""
        super().__init__(guardian, SWITCH_KIND_VALVE, "Valve", None, "mdi:water")

        self._is_on = True

    @property
    def is_on(self):
        """Return True if the valve is open."""
        return self._is_on

    @callback
    def _update_from_latest_data(self):
        """Update the entity."""
        self._is_on = self._guardian.data[DATA_VALVE_STATUS]["state"] in (
            "start_opening",
            "opening",
            "finish_opening",
            "opened",
        )

        self._attrs.update(
            {
                ATTR_AVG_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "average_current"
                ],
                ATTR_INST_CURRENT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current"
                ],
                ATTR_INST_CURRENT_DDT: self._guardian.data[DATA_VALVE_STATUS][
                    "instantaneous_current_ddt"
                ],
                ATTR_TRAVEL_COUNT: self._guardian.data[DATA_VALVE_STATUS][
                    "travel_count"
                ],
            }
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the valve off (closed)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.close()
        except GuardianError as err:
            LOGGER.error("Error while closing the valve: %s", err)
            return

        self._is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the valve on (open)."""
        try:
            async with self._guardian.client:
                await self._guardian.client.valve.open()
        except GuardianError as err:
            LOGGER.error("Error while opening the valve: %s", err)
            return

        self._is_on = True
        self.async_write_ha_state()

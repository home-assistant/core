"""Define a RainMachine-specific DataUpdateCoordinator."""
from datetime import timedelta

from regenmaschine.errors import RainMachineError

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_PROGRAMS,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DATA_ZONES,
    DATA_ZONES_DETAILS,
    LOGGER,
)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)


class RainMachineCoordinator(DataUpdateCoordinator):
    """Define a RainMachine DataUpdateCoordinator."""

    def __init__(self, hass, *, controller, api_category) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=controller.name,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

        self._api_category = api_category
        self._controller = controller

    async def _async_update_data(self) -> dict:
        """Execute an API request against a RainMachine controller."""
        try:
            if self._api_category == DATA_PROGRAMS:
                data = await self.controller.programs.all(include_inactive=True)
            elif self._api_category == DATA_PROVISION_SETTINGS:
                data = await self.controller.provisioning.settings()
            elif self._api_category == DATA_RESTRICTIONS_CURRENT:
                data = await self.controller.restrictions.current()
            elif self._api_category == DATA_RESTRICTIONS_UNIVERSAL:
                data = await self.controller.restrictions.universal()
            elif self._api_category == DATA_ZONES:
                zones_data = await self.controller.zones.all(include_inactive=True)
                # This API call needs to be separate from the DATA_ZONES one above because,
                # maddeningly, the zone details API call doesn't include the current
                # state of the zone:
                details_data = await self.controller.zones.all(
                    details=True, include_inactive=True
                )
                data = {DATA_ZONES: zones_data, DATA_ZONES_DETAILS: details_data}
        except RainMachineError as err:
            raise UpdateFailed(err) from err

        return data

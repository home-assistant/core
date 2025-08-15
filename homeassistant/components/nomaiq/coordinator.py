"""Coordinator for nomaiq."""

from datetime import timedelta

import ayla_iot_unofficial

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class NomaIQDataUpdateCoordinator(
    DataUpdateCoordinator[list[ayla_iot_unofficial.device.Device]]
):
    """Devices state update handler."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger,
        update_interval: timedelta,
        api: ayla_iot_unofficial.AylaApi,
    ) -> None:
        """Initialize global data updater."""
        self._api = api

        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
            update_method=self._async_update_data,
        )

    @property
    def api(self) -> ayla_iot_unofficial.AylaApi:
        """Return the API instance."""
        return self._api

    async def _async_update_data(self) -> list[ayla_iot_unofficial.device.Device]:
        """Fetch data."""
        try:
            try:
                self._api.check_auth()
            except ayla_iot_unofficial.AylaAuthExpiringError:
                await self._api.async_refresh_auth()
            except Exception as ex:
                self.logger.error("Failed to refresh auth: %s", ex)
                raise UpdateFailed("Failed to refresh auth") from ex

            devices = await self._api.async_get_devices()
            for device in devices:
                await device.async_update()
        except Exception as ex:
            raise UpdateFailed(f"Exception on getting states: {ex}") from ex
        else:
            return devices

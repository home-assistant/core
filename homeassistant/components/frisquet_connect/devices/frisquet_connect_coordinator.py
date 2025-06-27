from datetime import timedelta
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from frisquet_connect.domains.exceptions.forbidden_access_exception import (
    ForbiddenAccessException,
)
from frisquet_connect.domains.site.site import Site
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)


_LOGGER = logging.getLogger(__name__)


class FrisquetConnectCoordinator(DataUpdateCoordinator[Site]):
    _service: FrisquetConnectDevice
    _site_id: str

    def __init__(
        self, hass: HomeAssistant, service: FrisquetConnectDevice, site_id: str
    ):
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Frisquet Connect Coordinator",
            update_interval=timedelta(minutes=5),
            update_method=self._async_update_data,
            always_update=True,
        )
        self._service = service
        self._site_id = site_id

    async def _async_update_data(self):
        site_up_to_date = None
        try_count = 1
        while try_count >= 0:
            _LOGGER.debug(f"Fetching data for site {self._site_id} (try {try_count})")
            try_count -= 1
            try:
                site_up_to_date = await self._service.async_get_site_info(self._site_id)
                consumptions_site = await self._service.async_get_site_consumptions(
                    self._site_id
                )
                site_up_to_date._consumptions = consumptions_site._consumptions
                break
            except ForbiddenAccessException:
                await self._service.async_refresh_token_and_sites()
            except Exception as e:
                error_message = f"Error unknown during fetching data: {e}"
                raise UpdateFailed(error_message)
        return site_up_to_date

    @property
    def is_site_loaded(self) -> bool:
        return self.data is not None

    @property
    def service(self) -> FrisquetConnectDevice:
        return self._service

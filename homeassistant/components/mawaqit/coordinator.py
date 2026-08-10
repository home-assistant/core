"""Coordinators for the Mawaqit integration."""

from datetime import timedelta
import logging
from typing import override

from mawaqit import AsyncMawaqitClient
from mawaqit.exceptions import BadCredentialsException, MawaqitException

from homeassistant.const import CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .types import MawaqitConfigEntry

_LOGGER = logging.getLogger(__name__)


class MosqueCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch mosque information."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MawaqitConfigEntry,
        client: AsyncMawaqitClient,
    ) -> None:
        """Initialize the mosque coordinator."""
        self.client = client
        self.mosque_uuid: str = config_entry.data[CONF_UUID]

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Mosque Data",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch mosque details from the API."""
        mosque_data: dict | None
        try:
            mosque_data = await self.client.fetch_mosque_by_id(self.mosque_uuid)
        except BadCredentialsException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mawaqit_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except MawaqitException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mawaqit_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="network_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not mosque_data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_mosque_data",
            )

        return mosque_data


class PrayerTimeCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch prayer times from the Mawaqit API.

    The API is called twice a day to fetch the full prayer calendar.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MawaqitConfigEntry,
        client: AsyncMawaqitClient,
    ) -> None:
        """Initialize the prayer time coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Prayer Times",
            update_method=self._async_update_data,
            update_interval=timedelta(hours=12),
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch prayer times from API and notify sensors."""
        prayer_times: dict | None
        try:
            prayer_times = await self.client.fetch_prayer_times()
        except BadCredentialsException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mawaqit_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except MawaqitException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mawaqit_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="network_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not prayer_times:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_prayer_times_data",
            )

        # return fresh data when fetched
        return prayer_times

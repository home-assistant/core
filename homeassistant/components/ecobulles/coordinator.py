"""Data update coordinator for Ecobulles."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyecobulles import EcobullesClient

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import EcobullesConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EcobullesData:
    """Runtime data fetched from Ecobulles."""

    water_liters: int
    co2_injection_time_seconds: float
    last_updated: str | None


class EcobullesCoordinator(DataUpdateCoordinator[EcobullesData]):
    """Fetch Ecobulles cloud data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EcobullesClient,
        config_entry: EcobullesConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        assert config_entry.unique_id is not None
        self.api = api
        self.eco_ref = config_entry.unique_id
        super().__init__(
            hass,
            _LOGGER,
            name=f"Ecobulles {config_entry.data[CONF_EMAIL]}",
            update_interval=timedelta(seconds=120),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> EcobullesData:
        """Fetch Ecobulles data."""
        try:
            async with asyncio.timeout(15):
                usage = await self.api.get_total_water_and_co2_usage(self.eco_ref)
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except RuntimeError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if usage is None or "total_eau" not in usage or "total_gas" not in usage:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_payload_incomplete",
            )

        return EcobullesData(
            water_liters=usage["total_eau"],
            co2_injection_time_seconds=round(int(usage["total_gas"]) / 1000, 3),
            last_updated=usage.get("last_updated"),
        )

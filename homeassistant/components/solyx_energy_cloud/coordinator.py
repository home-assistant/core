"""Coordinator file that handles data updates for Solyx Energy device entities."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging
from typing import override

from solyx_energy_api.client import SolyxEnergyApiClient
from solyx_energy_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
    SolyxEnergyWriteError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTRIBUTE_BOILER_CURRENT,
    ATTRIBUTE_BOILER_POWER,
    ATTRIBUTE_BOILER_VOLTAGE,
    ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE,
    ATTRIBUTE_GRID_POWER,
    ATTRIBUTE_LEGIONELLA_DAYS,
    ATTRIBUTE_OPERATING_MODE,
    ATTRIBUTE_SAVED_THIS_MONTH,
    ATTRIBUTE_SAVED_THIS_WEEK,
    ATTRIBUTE_SAVED_TODAY,
    DATA_INTERVAL_SECONDS,
    DATA_SETTLE_SECONDS,
    DOMAIN,
)
from .util import parse_float, parse_str

_LOGGER = logging.getLogger(__name__)

type SolyxEnergyConfigEntry = ConfigEntry[SolyxEnergyCoordinator]


@dataclass(frozen=True)
class SolyxEnergyData:
    """Hold a snapshot of the values of a single Nymo device exposed to Home Assistant."""

    boiler_current: float | None
    boiler_power: float | None
    boiler_voltage: float | None
    days_since_maximum_temperature: float | None
    grid_power: float | None
    legionella_days: float | None
    operating_mode: str | None
    saved_this_month: float | None
    saved_this_week: float | None
    saved_today: float | None


class SolyxEnergyCoordinator(DataUpdateCoordinator[dict[str, SolyxEnergyData]]):
    """Coordinator that fetches data over HTTPS using the SolyxEnergyApiClient class."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: SolyxEnergyApiClient,
        config_entry: SolyxEnergyConfigEntry,
    ) -> None:
        """Initialize the main coordinator for the Solyx Energy integration."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DATA_INTERVAL_SECONDS),
        )
        self.api_client = api_client
        self._settle_unsub: CALLBACK_TYPE | None = None
        config_entry.async_on_unload(self._async_cancel_settle_timer)

    @override
    async def _async_update_data(self) -> dict[str, SolyxEnergyData]:
        """Fetch data with the SolyxEnergyApiClient class and update the device entities accordingly."""
        try:
            _LOGGER.debug("Retrieving data from Solyx Energy API")
            assets = await self.api_client.async_get_assets()
        except SolyxEnergyAuthError as err:
            raise ConfigEntryAuthFailed(f"Auth error: {err}") from err
        except (SolyxEnergyTokenError, SolyxEnergyDataError) as err:
            raise UpdateFailed(f"API error: {err}") from err

        return {
            asset["id"]: SolyxEnergyData(
                boiler_current=parse_float(asset, ATTRIBUTE_BOILER_CURRENT),
                boiler_power=parse_float(asset, ATTRIBUTE_BOILER_POWER),
                boiler_voltage=parse_float(asset, ATTRIBUTE_BOILER_VOLTAGE),
                days_since_maximum_temperature=parse_float(
                    asset, ATTRIBUTE_DAYS_SINCE_MAX_TEMPERATURE
                ),
                grid_power=parse_float(asset, ATTRIBUTE_GRID_POWER),
                legionella_days=parse_float(asset, ATTRIBUTE_LEGIONELLA_DAYS),
                operating_mode=parse_str(asset, ATTRIBUTE_OPERATING_MODE),
                saved_this_month=parse_float(asset, ATTRIBUTE_SAVED_THIS_MONTH),
                saved_this_week=parse_float(asset, ATTRIBUTE_SAVED_THIS_WEEK),
                saved_today=parse_float(asset, ATTRIBUTE_SAVED_TODAY),
            )
            for asset in assets
        }

    async def async_set_operating_mode(self, device_id: str, mode: str) -> None:
        """Push a new operating mode for a Nymo device to the Solyx Energy cloud."""
        await self._async_set_attribute(
            device_id,
            ATTRIBUTE_OPERATING_MODE,
            mode,
            lambda data: replace(data, operating_mode=mode),
        )

    async def _async_set_attribute(
        self,
        device_id: str,
        attribute_name: str,
        value: object,
        update_data_fn: Callable[[SolyxEnergyData], SolyxEnergyData],
    ) -> None:
        """Push data from a device entity to the Solyx cloud platform and optimistically apply it."""
        try:
            _LOGGER.debug(
                "Updating attribute %s of device %s to %s",
                attribute_name,
                device_id,
                value,
            )
            await self.api_client.async_set_asset_attribute(
                device_id, attribute_name, value
            )
        except SolyxEnergyAuthError as err:
            raise ConfigEntryAuthFailed(f"Auth error: {err}") from err
        except (SolyxEnergyTokenError, SolyxEnergyWriteError) as err:
            raise HomeAssistantError(f"API error: {err}") from err

        # Assume the data from the control is correct.
        if (data := self.data.get(device_id)) is not None:
            self.async_set_updated_data({**self.data, device_id: update_data_fn(data)})

        # After the data has settled on the Solyx cloud platform, retrieve the
        # actual data through the SolyxEnergyApiClient class.
        if self._settle_unsub is not None:
            self._settle_unsub()
        self._settle_unsub = async_call_later(
            self.hass, DATA_SETTLE_SECONDS, self._async_settle_refresh
        )

    async def _async_settle_refresh(self, _now: datetime) -> None:
        """Refresh the data after a write has settled on the Solyx cloud platform."""
        self._settle_unsub = None
        await self.async_request_refresh()

    @callback
    def _async_cancel_settle_timer(self) -> None:
        """Cancel a pending settle timer when the config entry is unloaded."""
        if self._settle_unsub is not None:
            self._settle_unsub()
            self._settle_unsub = None

"""Data updates for IAMMETER."""

from datetime import timedelta
import logging
from typing import Any, override

from iammeter.client import IamMeter
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEVICE_TYPES

_LOGGER = logging.getLogger(__name__)

type IammeterConfigEntry = ConfigEntry[IammeterDataUpdateCoordinator]


class InvalidDataError(ValueError):
    """The endpoint did not return supported meter data."""


def validate_data(data: dict[str, Any]) -> None:
    """Check the identity needed to register the meter."""
    if (
        not isinstance(data.get("sn"), str)
        or not data["sn"].strip()
        or data.get("Model") not in DEVICE_TYPES
    ):
        raise InvalidDataError("Missing serial number or unsupported meter model")


async def async_get_meter(hass: HomeAssistant, data: dict[str, Any]) -> IamMeter:
    """Connect and read the meter once outside the event loop."""
    try:
        api = await hass.async_add_executor_job(
            IamMeter, data[CONF_HOST], data.get(CONF_PORT, DEFAULT_PORT)
        )
    except (KeyError, IndexError, TypeError, UnboundLocalError) as err:
        raise InvalidDataError("Invalid meter response") from err
    validate_data(api.measurement)
    return api


class IammeterDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate local meter readings."""

    def __init__(self, hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self._entry = entry
        self._api: IamMeter | None = None

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data and reject a replaced device."""
        try:
            if self._api is None:
                self._api = await async_get_meter(self.hass, dict(self._entry.data))
                data = self._api.measurement
            else:
                data = await self.hass.async_add_executor_job(self._api.client.get_data)
                validate_data(data)
        except (
            RequestException,
            TimeoutError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            UnboundLocalError,
        ) as err:
            raise UpdateFailed("Unable to read meter data") from err
        if data["sn"] != self._entry.unique_id:
            raise UpdateFailed("The meter serial number has changed")
        return data

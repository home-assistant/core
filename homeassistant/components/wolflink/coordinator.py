"""DataUpdateCoordinator for the Wolf SmartSet Service integration."""

from datetime import timedelta
import logging

from httpx import RequestError
from wolf_comm.models import Parameter
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import FetchFailed, ParameterReadError, WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WolfLinkCoordinator(DataUpdateCoordinator[dict[int, tuple[int, str]]]):
    """Class to manage fetching Wolf SmartSet data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        wolf_client: WolfClient,
        parameters: list[Parameter],
        gateway_id: int,
        device_id: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._wolf_client = wolf_client
        self._parameters = parameters
        self._gateway_id = gateway_id
        self._device_id = device_id
        self._refetch_parameters = False

    async def _async_update_data(self) -> dict[int, tuple[int, str]]:
        """Update all stored entities for Wolf SmartSet."""
        try:
            if not await self._wolf_client.fetch_system_state_list(
                self._device_id, self._gateway_id
            ):
                self._refetch_parameters = True
                raise UpdateFailed(
                    "Could not fetch values from server because device is offline."
                )
            if self._refetch_parameters:
                self._parameters = await fetch_parameters(
                    self._wolf_client, self._gateway_id, self._device_id
                )
                self._refetch_parameters = False
            values = {
                v.value_id: v.value
                for v in await self._wolf_client.fetch_value(
                    self._gateway_id, self._device_id, self._parameters
                )
            }
            return {
                parameter.parameter_id: (
                    parameter.value_id,
                    values[parameter.value_id],
                )
                for parameter in self._parameters
                if parameter.value_id in values
            }
        except RequestError as exception:
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception
        except FetchFailed as exception:
            raise UpdateFailed(
                f"Could not fetch values from server due to: {exception}"
            ) from exception
        except ParameterReadError as exception:
            self._refetch_parameters = True
            raise UpdateFailed(
                "Could not fetch values for parameter. Refreshing value IDs."
            ) from exception
        except InvalidAuth as exception:
            raise UpdateFailed("Invalid authentication during update.") from exception


async def fetch_parameters(
    client: WolfClient, gateway_id: int, device_id: int
) -> list[Parameter]:
    """Fetch all available parameters with usage of WolfClient.

    By default Reglertyp entity is removed because API will not provide value for this parameter.
    """
    fetched_parameters = await client.fetch_parameters(gateway_id, device_id)
    return [param for param in fetched_parameters if param.name != "Reglertyp"]

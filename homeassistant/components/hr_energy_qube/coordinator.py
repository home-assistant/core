"""DataUpdateCoordinator for Qube Heat Pump."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from python_qube_heatpump import QubeClient
from python_qube_heatpump.models import QubeState

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@dataclass
class QubeData:
    """Data from the Qube coordinator."""

    state: QubeState
    switches: dict[str, bool | None]


class QubeCoordinator(DataUpdateCoordinator[QubeData]):
    """Qube Heat Pump data coordinator."""

    def __init__(
        self, hass: HomeAssistant, client: QubeClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )

    async def _async_update_data(self) -> QubeData:
        """Fetch data from the device."""
        try:
            state = await self.client.get_all_data()
            switches = await self.client.read_all_switches()
        except (ConnectionError, TimeoutError, OSError) as exc:
            raise UpdateFailed(
                f"Error communicating with Qube heat pump: {exc}"
            ) from exc

        if state is None:
            raise UpdateFailed("No data received from Qube heat pump")

        return QubeData(state=state, switches=switches)

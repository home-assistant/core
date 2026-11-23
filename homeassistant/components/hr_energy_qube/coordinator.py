"""DataUpdateCoordinator for Qube Heat Pump."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from python_qube_heatpump import QubeClient
from python_qube_heatpump.models import QubeState

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SW_VERSION, DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import QubeConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class QubeData:
    """Data from the Qube coordinator."""

    state: QubeState
    switches: dict[str, bool | None]
    sg_ready_mode: str | None


class QubeCoordinator(DataUpdateCoordinator[QubeData]):
    """Qube Heat Pump data coordinator."""

    config_entry: QubeConfigEntry
    sw_version: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        client: QubeClient,
        entry: QubeConfigEntry,
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

    @override
    async def _async_setup(self) -> None:
        """Read the software version; the first request opens the connection."""
        self.sw_version = await self.client.async_get_software_version()
        if not self.client.is_connected:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.client.host},
            )
        # Register 77 reads 0 on recent firmware; the version on the panel is
        # only in the mDNS record, which discovery stores with the entry
        if sw_version := self.config_entry.data.get(CONF_SW_VERSION):
            self.sw_version = sw_version

    @override
    async def _async_update_data(self) -> QubeData:
        """Fetch data from the device."""
        try:
            state = await self.client.get_all_data()
            switches = await self.client.read_all_switches()
            sg_ready_mode = await self.client.get_sg_ready_mode()
        except OSError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(exc)},
            ) from exc

        if state is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data",
            )

        return QubeData(state=state, switches=switches, sg_ready_mode=sg_ready_mode)

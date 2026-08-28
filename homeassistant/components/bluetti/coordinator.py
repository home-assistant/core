"""DataUpdateCoordinator for the BLUETTI integration's cloud data."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from pybluetti import ApplicationRuntimeException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import BluettiDevice

if TYPE_CHECKING:
    # Not a runtime import - __init__.py imports this module, so this
    # would be circular.
    from . import BluettiConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

# msgCode values that mean the OAuth token is no longer valid.
AUTH_ERROR_CODES = {401, 805}


class BluettiDeviceCoordinator(DataUpdateCoordinator[BluettiDevice]):
    """Coordinate REST polling and websocket-triggered refreshes for one device."""

    def __init__(
        self, hass: HomeAssistant, entry: BluettiConfigEntry, device: BluettiDevice
    ) -> None:
        """Initialize the coordinator for a single BLUETTI device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"bluetti-{device.device_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        device.coordinator = self

    @override
    async def _async_update_data(self) -> BluettiDevice:
        """Fetch the latest state for the device from the BLUETTI cloud API."""
        try:
            await self.device.async_refresh_from_api()
        except ApplicationRuntimeException as err:
            if err.msgCode in AUTH_ERROR_CODES:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_expired",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return self.device

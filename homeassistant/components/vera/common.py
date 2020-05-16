"""Common vera code."""
from datetime import timedelta
import logging
from typing import DefaultDict, List, NamedTuple, Set

import pyvera as pv

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ControllerData(NamedTuple):
    """Controller data."""

    controller: pv.VeraController
    devices: DefaultDict[str, List[pv.VeraDevice]]
    scenes: List[pv.VeraScene]


def get_configured_platforms(controller_data: ControllerData) -> Set[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices:
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)


class UpdateCoordinatorData(NamedTuple):
    """Data provided by the update coordinator."""

    lu_sdata: dict
    status: dict


class SubscriptionRegistry(pv.AbstractSubscriptionRegistry):
    """Manages polling for data from vera."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the object."""
        super().__init__()
        self._hass = hass
        self._update_coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name="vera",
            update_interval=timedelta(seconds=1),
            update_method=self._async_fetch_data,
        )

    def start(self) -> None:
        """Start polling for data."""
        self._update_coordinator.async_add_listener(self._async_on_data_updated)

    def stop(self) -> None:
        """Stop polling for data."""
        self._update_coordinator.async_remove_listener(self._async_on_data_updated)

    async def _async_fetch_data(self) -> UpdateCoordinatorData:
        if not self._controller:
            raise pv.ControllerNotSetException()

        lu_sdata_respone = await self._hass.async_add_executor_job(
            self.get_controller().data_request,
            {"id": "lu_sdata", "output_format": "json"},
        )

        status_response = await self._hass.async_add_executor_job(
            self.get_controller().data_request,
            {"id": "status", "output_format": "json"},
        )

        return UpdateCoordinatorData(
            lu_sdata=lu_sdata_respone.json(), status=status_response.json(),
        )

    def _async_on_data_updated(self) -> None:
        self._hass.async_add_executor_job(self.poll_server_once)

    def get_device_data(self, last_updated: dict) -> pv.ChangedDevicesValue:
        """Get device data."""
        return (
            self._update_coordinator.data.lu_sdata.get("devices", []),
            # Return static version data, always_update() renders version checking useless.
            {"dataversion": 1, "loadtime": 0},
        )

    def get_alert_data(self, last_updated: dict) -> List[dict]:
        """Get alert data."""
        return self._update_coordinator.data.status.get("alerts", [])

    def always_update(self) -> bool:  # pylint: disable=no-self-use
        """Determine if we should treat every poll as a data change."""
        # Ignore incremental checks for data changes.
        return True

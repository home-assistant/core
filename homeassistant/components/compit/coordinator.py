"""Define an object to manage fetching Compit data."""

from datetime import timedelta
import logging

from compit_inext_api import (
    CompitAPI,
    DeviceDefinitions,
    DeviceInstance,
    DeviceState,
    Gate,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER: logging.Logger = logging.getLogger(__package__)


class CompitDataUpdateCoordinator(DataUpdateCoordinator[dict[int, DeviceInstance]]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        gates: list[Gate],
        api: CompitAPI,
        device_definitions: DeviceDefinitions,
    ) -> None:
        """Initialize."""
        self.devices: dict[int, DeviceInstance] = {}
        self.api = api
        self.gates = gates
        self.device_definitions = device_definitions

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> dict[int, DeviceInstance]:
        """Update data via library."""

        for gate in self.gates:
            _LOGGER.debug("Gate: %s, Code: %s", gate.label, gate.code)
            for device in gate.devices:
                if device.id not in self.devices:
                    device_definition = next(
                        (
                            item
                            for item in self.device_definitions.devices
                            if item.device_class == device.device_class
                            and item.code == device.type
                        ),
                        None,
                    )
                    if device_definition is None:
                        _LOGGER.warning(
                            "Device definition not found for device %s, class: %s, type: %s",
                            device.label,
                            device.device_class,
                            device.type,
                        )
                        continue
                    self.devices[device.id] = DeviceInstance(device_definition)

                _LOGGER.debug(
                    "Device: %s, id: %s, class: %s, type: %s",
                    device.label,
                    device.id,
                    device.device_class,
                    device.type,
                )
                try:
                    state = await self.api.get_state(device.id)

                    if state and state is DeviceState:
                        self.devices[device.id].state = state
                    else:
                        _LOGGER.error("Failed to get state for device %s", device.id)
                except ValueError as exception:
                    raise UpdateFailed from exception
        return self.devices

"""Base class for Switcher entities."""

import logging
from typing import Any

from aioswitcher.api import SwitcherApi
from aioswitcher.api.messages import SwitcherBaseResponse

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SwitcherDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SwitcherEntity(CoordinatorEntity[SwitcherDataUpdateCoordinator]):
    """Base class for Switcher entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_data()
        super()._handle_coordinator_update()

    def _update_data(self) -> None:
        """Update data from device."""

    async def _async_call_api(self, api: str, *args: Any, **kwargs: Any) -> None:
        """Call Switcher API."""
        _LOGGER.debug("Calling api for %s, api: '%s', args: %s", self.name, api, args)
        response: SwitcherBaseResponse | None = None
        error = None

        try:
            async with SwitcherApi(
                self.coordinator.data.device_type,
                self.coordinator.data.ip_address,
                self.coordinator.data.device_id,
                self.coordinator.data.device_key,
                self.coordinator.token,
            ) as swapi:
                response = await getattr(swapi, api)(*args, **kwargs)
        except (TimeoutError, OSError, RuntimeError) as err:
            error = repr(err)

        if error or not response or not response.successful:
            self.coordinator.last_update_success = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Call api for {self.name} failed, api: '{api}', "
                f"args: {args}, response/error: {response or error}"
            )

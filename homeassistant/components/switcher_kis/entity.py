"""Base class for Switcher entities."""

import logging
from typing import Any, override

from aioswitcher.api import SwitcherApi
from aioswitcher.api.messages import SwitcherBaseResponse

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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
    @override
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

        # Availability is driven by the device broadcasts, so surface failures
        # without marking the entity unavailable.
        try:
            async with SwitcherApi(
                self.coordinator.data.device_type,
                self.coordinator.data.ip_address,
                self.coordinator.data.device_id,
                self.coordinator.data.device_key,
                self.coordinator.token,
            ) as swapi:
                response = await getattr(swapi, api)(*args, **kwargs)
        except (TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"entity": str(self.name)},
            ) from err
        except RuntimeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"entity": str(self.name)},
            ) from err

        if not response or not response.successful:
            _LOGGER.debug("Unsuccessful response from %s: %s", self.name, response)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"entity": str(self.name)},
            )

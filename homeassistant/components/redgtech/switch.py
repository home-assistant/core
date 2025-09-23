"""Integration for Redgtech switches."""

from __future__ import annotations

import logging
from typing import Any

from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RedgtechConfigEntry, RedgtechDataUpdateCoordinator
from .device import RedgtechDevice

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RedgtechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        RedgtechSwitch(coordinator, device) for device in coordinator.data
    )


class RedgtechSwitch(CoordinatorEntity[RedgtechDataUpdateCoordinator], SwitchEntity):
    """Representation of a Redgtech switch."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: RedgtechDataUpdateCoordinator, device: RedgtechDevice
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.device = device
        self._attr_unique_id = device.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer="Redgtech",
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return False

        for device in self.coordinator.data:
            if device.unique_id == self.device.unique_id:
                return bool(device.state)

        return False

    async def _set_state(self, new_state: bool) -> None:
        """Set state of the switch."""
        try:
            await self.coordinator.ensure_token()

            await self.coordinator.api.set_switch_state(
                self.device.unique_id, new_state, self.coordinator.access_token
            )

            await self.coordinator.async_refresh()
        except RedgtechAuthError as err:
            _LOGGER.error(
                "Failed to set switch state due to authentication error: %s", err
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="switch_auth_error"
            ) from err
        except RedgtechConnectionError as err:
            _LOGGER.error("Connection error: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="connection_error"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_state(False)

"""Integration for Redgtech switches."""

from __future__ import annotations

import logging
from typing import Any

from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    RedgtechConfigEntry,
    RedgtechDataUpdateCoordinator,
    RedgtechDevice,
)

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
        return self.device.state == STATE_ON

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        new_state = not self.is_on

        try:
            if not self.coordinator.access_token:
                self.coordinator.access_token = await self.coordinator.login(
                    self.coordinator.email, self.coordinator.password
                )

            await self.coordinator.api.set_switch_state(
                self.device.unique_id, new_state, self.coordinator.access_token
            )

            self.device.state = STATE_ON if new_state else STATE_OFF
            self.async_write_ha_state()

        except RedgtechAuthError:
            try:
                await self.coordinator.renew_token(
                    self.coordinator.email, self.coordinator.password
                )
                await self.coordinator.api.set_switch_state(
                    self.device.unique_id, new_state, self.coordinator.access_token
                )

                self.device.state = STATE_ON if new_state else STATE_OFF
                self.async_write_ha_state()
            except RedgtechAuthError as e:
                raise HomeAssistantError(
                    "Failed to set switch state due to authentication error"
                ) from e
        except RedgtechConnectionError as e:
            raise HomeAssistantError(
                "Connection error while setting switch state"
            ) from e

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.is_on:
            await self.async_toggle()
        else:
            pass

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.is_on:
            await self.async_toggle()
        else:
            pass

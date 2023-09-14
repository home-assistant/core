"""Base ScreenLogicEntity definitions."""
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from screenlogicpy import ScreenLogicGateway
from screenlogicpy.const.common import ON_OFF
from screenlogicpy.const.data import ATTR
from screenlogicpy.const.msg import CODE

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ScreenLogicDataPath
from .coordinator import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class ScreenLogicEntityRequiredKeyMixin:
    """Mixin for required ScreenLogic entity key."""

    data_path: ScreenLogicDataPath


@dataclass
class ScreenLogicEntityDescription(
    EntityDescription, ScreenLogicEntityRequiredKeyMixin
):
    """Base class for a ScreenLogic entity description."""


class ScreenlogicEntity(CoordinatorEntity[ScreenlogicDataUpdateCoordinator]):
    """Base class for all ScreenLogic entities."""

    entity_description: ScreenLogicEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicEntityDescription,
    ) -> None:
        """Initialize of the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._data_path = self.entity_description.data_path
        self._data_key = self._data_path[-1]
        self._attr_unique_id = f"{self.mac}_{self.entity_description.key}"
        mac = self.mac
        assert mac is not None
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            manufacturer="Pentair",
            model=self.gateway.controller_model,
            name=self.gateway.name,
            sw_version=self.gateway.version,
        )

    @property
    def mac(self) -> str | None:
        """Mac address."""
        assert self.coordinator.config_entry is not None
        return self.coordinator.config_entry.unique_id

    @property
    def gateway(self) -> ScreenLogicGateway:
        """Return the gateway."""
        return self.coordinator.gateway

    async def _async_refresh(self) -> None:
        """Refresh the data from the gateway."""
        await self.coordinator.async_refresh()
        # Second debounced refresh to catch any secondary
        # changes in the device
        await self.coordinator.async_request_refresh()

    async def _async_refresh_timed(self, now: datetime) -> None:
        """Refresh from a timed called."""
        await self.coordinator.async_request_refresh()

    @property
    def entity_data(self) -> dict:
        """Shortcut to the data for this entity."""
        if (data := self.gateway.get_data(*self._data_path)) is None:
            raise KeyError(f"Data not found: {self._data_path}")
        return data


@dataclass
class ScreenLogicPushEntityRequiredKeyMixin:
    """Mixin for required key for ScreenLogic push entities."""

    subscription_code: CODE


@dataclass
class ScreenLogicPushEntityDescription(
    ScreenLogicEntityDescription,
    ScreenLogicPushEntityRequiredKeyMixin,
):
    """Base class for a ScreenLogic push entity description."""


class ScreenLogicPushEntity(ScreenlogicEntity):
    """Base class for all ScreenLogic push entities."""

    entity_description: ScreenLogicPushEntityDescription

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        entity_description: ScreenLogicPushEntityDescription,
    ) -> None:
        """Initialize of the entity."""
        super().__init__(coordinator, entity_description)
        self._last_update_success = True

    @callback
    def _async_data_updated(self) -> None:
        """Handle data updates."""
        self._last_update_success = self.coordinator.last_update_success
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            await self.gateway.async_subscribe_client(
                self._async_data_updated,
                self.entity_description.subscription_code,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # For push entities, only take updates from the coordinator if availability changes.
        if self.coordinator.last_update_success != self._last_update_success:
            self._async_data_updated()


class ScreenLogicCircuitEntity(ScreenLogicPushEntity):
    """Base class for all ScreenLogic switch and light entities."""

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.entity_data[ATTR.VALUE] == ON_OFF.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the ON command."""
        await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the OFF command."""
        await self._async_set_circuit(ON_OFF.OFF)

    async def _async_set_circuit(self, state: ON_OFF) -> None:
        if not await self.gateway.async_set_circuit(self._data_key, state.value):
            raise HomeAssistantError(
                f"Failed to set_circuit {self._data_key} {state.value}"
            )
        _LOGGER.debug("Set circuit %s %s", self._data_key, state.value)

"""Base ScreenLogicEntity definitions."""
from datetime import datetime
import logging
from typing import Any

from screenlogicpy import ScreenLogicGateway
from screenlogicpy.const import CODE, DATA as SL_DATA, EQUIPMENT, ON_OFF

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ScreenlogicEntity(CoordinatorEntity[ScreenlogicDataUpdateCoordinator]):
    """Base class for all ScreenLogic entities."""

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        data_key: str,
        enabled: bool = True,
    ) -> None:
        """Initialize of the entity."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_entity_registry_enabled_default = enabled
        self._attr_unique_id = f"{self.mac}_{self._data_key}"

        controller_type = self.config_data["controller_type"]
        hardware_type = self.config_data["hardware_type"]
        try:
            equipment_model = EQUIPMENT.CONTROLLER_HARDWARE[controller_type][
                hardware_type
            ]
        except KeyError:
            equipment_model = f"Unknown Model C:{controller_type} H:{hardware_type}"
        mac = self.mac
        assert mac is not None
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            manufacturer="Pentair",
            model=equipment_model,
            name=self.gateway_name,
            sw_version=self.gateway.version,
        )

    @property
    def mac(self) -> str | None:
        """Mac address."""
        assert self.coordinator.config_entry is not None
        return self.coordinator.config_entry.unique_id

    @property
    def config_data(self) -> dict[str | int, Any]:
        """Shortcut for config data."""
        return self.gateway_data[SL_DATA.KEY_CONFIG]

    @property
    def gateway(self) -> ScreenLogicGateway:
        """Return the gateway."""
        return self.coordinator.gateway

    @property
    def gateway_data(self) -> dict[str | int, Any]:
        """Return the gateway data."""
        return self.gateway.get_data()

    @property
    def gateway_name(self) -> str:
        """Return the configured name of the gateway."""
        return self.gateway.name

    async def _async_refresh(self) -> None:
        """Refresh the data from the gateway."""
        await self.coordinator.async_refresh()
        # Second debounced refresh to catch any secondary
        # changes in the device
        await self.coordinator.async_request_refresh()

    async def _async_refresh_timed(self, now: datetime) -> None:
        """Refresh from a timed called."""
        await self.coordinator.async_request_refresh()


class ScreenLogicPushEntity(ScreenlogicEntity):
    """Base class for all ScreenLogic push entities."""

    def __init__(
        self,
        coordinator: ScreenlogicDataUpdateCoordinator,
        data_key: str,
        message_code: CODE,
        enabled: bool = True,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, data_key, enabled)
        self._update_message_code = message_code
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
                self._async_data_updated, self._update_message_code
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

    _attr_has_entity_name = True

    @property
    def name(self) -> str:
        """Get the name of the switch."""
        return self.circuit["name"]

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["value"] == ON_OFF.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the ON command."""
        await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the OFF command."""
        await self._async_set_circuit(ON_OFF.OFF)

    async def _async_set_circuit(self, circuit_value: int) -> None:
        if not await self.gateway.async_set_circuit(self._data_key, circuit_value):
            raise HomeAssistantError(
                f"Failed to set_circuit {self._data_key} {circuit_value}"
            )
        _LOGGER.debug("Turn %s %s", self._data_key, circuit_value)

    @property
    def circuit(self) -> dict[str | int, Any]:
        """Shortcut to access the circuit."""
        return self.gateway_data[SL_DATA.KEY_CIRCUITS][self._data_key]

"""Base ScreenLogicEntity definitions."""
import logging

# from screenlogicpy import ScreenLogicError, ScreenLogicGateway
from screenlogicpy.const import DATA as SL_DATA, EQUIPMENT, ON_OFF

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ScreenlogicDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ScreenlogicEntity(CoordinatorEntity[ScreenlogicDataUpdateCoordinator]):
    """Base class for all ScreenLogic entities."""

    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._enabled_default = enabled

    @property
    def entity_registry_enabled_default(self):
        """Entity enabled by default."""
        return self._enabled_default

    @property
    def mac(self):
        """Mac address."""
        return self.coordinator.config_entry.unique_id

    @property
    def unique_id(self):
        """Entity Unique ID."""
        return f"{self.mac}_{self._data_key}"

    @property
    def config_data(self):
        """Shortcut for config data."""
        return self.coordinator.gateway.get_data()[SL_DATA.KEY_CONFIG]

    @property
    def gateway(self):
        """Return the gateway."""
        return self.coordinator.gateway

    @property
    def gateway_name(self):
        """Return the configured name of the gateway."""
        return self.gateway.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the controller."""
        controller_type = self.config_data["controller_type"]
        hardware_type = self.config_data["hardware_type"]
        try:
            equipment_model = EQUIPMENT.CONTROLLER_HARDWARE[controller_type][
                hardware_type
            ]
        except KeyError:
            equipment_model = f"Unknown Model C:{controller_type} H:{hardware_type}"
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac)},
            manufacturer="Pentair",
            model=equipment_model,
            name=self.gateway_name,
            sw_version=self.gateway.version,
        )

    async def _async_refresh(self):
        """Refresh the data from the gateway."""
        await self.coordinator.async_refresh()
        # Second debounced refresh to catch any secondary
        # changes in the device
        await self.coordinator.async_request_refresh()

    async def _async_refresh_timed(self, now):
        """Refresh from a timed called."""
        await self.coordinator.async_request_refresh()


class ScreenLogicPushEntity(ScreenlogicEntity):
    """Base class for all ScreenLogic push entities."""

    def __init__(self, coordinator, data_key, message_code, enabled=True):
        """Initialize the entity."""
        super().__init__(coordinator, data_key, enabled)
        self._update_message_code = message_code

    @callback
    def _async_data_updated(self) -> None:
        """Handle data updates."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""

        unsub = await self.coordinator.gateway.async_subscribe_client(
            self._async_data_updated, self._update_message_code
        )
        self.async_on_remove(unsub)


class ScreenLogicCircuitEntity(ScreenLogicPushEntity):
    """Base class for all ScreenLogic switch and light entities."""

    _attr_has_entity_name = True

    @property
    def name(self):
        """Get the name of the switch."""
        return self.circuit["name"]

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["value"] == ON_OFF.ON

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        await self._async_set_circuit(ON_OFF.OFF)

    async def _async_set_circuit(self, circuit_value) -> None:
        if await self.gateway.async_set_circuit(self._data_key, circuit_value):
            _LOGGER.debug("Turn %s %s", self._data_key, circuit_value)
        else:
            _LOGGER.warning(
                "Failed to set_circuit %s %s", self._data_key, circuit_value
            )

    @property
    def circuit(self):
        """Shortcut to access the circuit."""
        return self.coordinator.gateway.get_data()[SL_DATA.KEY_CIRCUITS][self._data_key]

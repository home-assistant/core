"""An abstract class common to all Switchbot entities."""

from collections.abc import Callable, Coroutine, Mapping
import logging
from typing import Any, Concatenate, override

from bleak.exc import BleakError
import switchbot
from switchbot import Switchbot, SwitchbotDevice, SwitchbotOperationError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, MANUFACTURER
from .coordinator import SwitchbotDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SwitchbotEntity(
    PassiveBluetoothCoordinatorEntity[SwitchbotDataUpdateCoordinator]
):
    """Generic entity encapsulating common features of Switchbot device."""

    _device: SwitchbotDevice
    _attr_has_entity_name = True

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._last_run_success: bool | None = None
        self._address = coordinator.ble_device.address
        self._attr_unique_id = coordinator.base_unique_id
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            manufacturer=MANUFACTURER,
            # Sometimes the modelName is missing from ads
            model=coordinator.model,
            name=coordinator.device_name,
        )
        self._channel: int | None = None
        if ":" not in self._address:
            # MacOS Bluetooth addresses are not mac addresses
            return
        # If the bluetooth address is also a mac address,
        # add this connection as well to prevent a new device
        # entry from being created when upgrading from a previous
        # version of the integration.
        self._attr_device_info[ATTR_CONNECTIONS].add(
            (dr.CONNECTION_NETWORK_MAC, self._address)
        )

    @property
    def parsed_data(self) -> dict[str, Any]:
        """Return parsed device data for this entity."""
        if isinstance(self.coordinator.device, switchbot.SwitchbotRelaySwitch2PM):
            return self.coordinator.device.get_parsed_data(self._channel)
        return self.coordinator.device.parsed_data

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(self._device.subscribe(self._handle_coordinator_update))
        return await super().async_added_to_hass()

    @override
    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._device.update()


class SwitchbotConnectionPolledEntity(SwitchbotEntity):
    """Entity whose value has to be read from the device over a connection.

    Reading needs an active connection, which is slow and frequently
    impossible while Home Assistant is still starting up and competing for the
    Bluetooth adapter, so the first read is deferred until startup is over.
    """

    _attr_should_poll = True
    _attr_entity_registry_enabled_default = False

    async def _async_read_value(self) -> None:
        """Read the value from the device into the entity attributes."""
        raise NotImplementedError

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks and read the value once startup is over."""
        await super().async_added_to_hass()
        self.async_on_remove(async_at_started(self.hass, self._async_hass_started))

    @callback
    def _async_hass_started(self, _hass: HomeAssistant) -> None:
        """Read the value now that startup is no longer in the way."""
        # A background task so a stuck connect is cancelled when the entry
        # unloads instead of holding up shutdown.
        self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self.async_update_ha_state(force_refresh=True),
            f"switchbot read {self.entity_id}",
        )

    @override
    async def async_update(self) -> None:
        """Read the value from the device."""
        if not bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        ):
            _LOGGER.debug("No connectable path to %s, skipping update", self._address)
            return
        try:
            await self._async_read_value()
        except SwitchbotOperationError, BleakError:
            _LOGGER.debug(
                "Failed to read %s from %s",
                self.entity_id,
                self._address,
                exc_info=True,
            )
            return


def exception_handler[_EntityT: SwitchbotEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Switchbot calls to handle exceptions..

    A decorator that wraps the passed in function, catches Switchbot errors.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except SwitchbotOperationError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="operation_error",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler


class SwitchbotSwitchedEntity(SwitchbotEntity, ToggleEntity):
    """Base class for Switchbot entities that can be turned on and off."""

    _device: Switchbot

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.debug("Turn Switchbot device on %s", self._address)

        self._last_run_success = bool(await self._device.turn_on())
        if self._last_run_success:
            self._attr_is_on = True
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.debug("Turn Switchbot device off %s", self._address)

        self._last_run_success = bool(await self._device.turn_off())
        if self._last_run_success:
            self._attr_is_on = False
        self.async_write_ha_state()

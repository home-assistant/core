"""Coordinator for oralb integration."""
import logging

from home_assistant_bluetooth import BluetoothServiceInfoBleak
from oralb_ble import OralBBluetoothDeviceData, SensorUpdate as OralBSensorUpdate

from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.components.bluetooth.api import async_ble_device_from_address
from homeassistant.components.bluetooth.models import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothEntityKey,
)
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)


class OralbActiveBluetoothProcessorCoordinator(ActiveBluetoothProcessorCoordinator):
    """Coordinator to handle Oral-B bluetooth connections."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
    ) -> None:
        """Create a Oralb coordinator."""
        self.oralb_data = OralBBluetoothDeviceData()
        self._active_subscriptions: set[PassiveBluetoothEntityKey] = set()
        super().__init__(
            hass,
            _LOGGER,
            address=address,
            mode=BluetoothScanningMode.PASSIVE,
            update_method=self.oralb_data.update,
            needs_poll_method=self._async_needs_poll_oralb,
            poll_method=self._async_poll_oralb,
            # We will take advertisements from non-connectable devices
            # since we will trade the BLEDevice for a connectable one
            # if we need to poll it
            connectable=False,
        )

    @callback
    def _async_needs_poll_oralb(
        self, service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        # and we have any subscribed entities
        return (
            self.hass.state == CoreState.running
            and self.needs_active_update
            and self.oralb_data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll_oralb(
        self, service_info: BluetoothServiceInfoBleak
    ) -> OralBSensorUpdate:
        # BluetoothServiceInfoBleak is defined in HA, otherwise would just pass it
        # directly to the oralb code
        # Make sure the device we have is one that we can connect with
        # in case its coming from a passive scanner
        if service_info.connectable:
            connectable_device = service_info.device
        elif device := async_ble_device_from_address(
            self.hass, service_info.device.address, True
        ):
            connectable_device = device
        else:
            # We have no bluetooth controller that is in range of
            # the device to poll it
            raise RuntimeError(
                f"No connectable device found for {service_info.device.address}"
            )
        return await self.oralb_data.async_poll(connectable_device)

    def register_active(self, sub: PassiveBluetoothEntityKey) -> CALLBACK_TYPE:
        """Register any entities that require a active connection."""
        self._active_subscriptions.add(sub)

        def _unregister() -> None:
            """Remove a subscription on entity removal."""
            self._active_subscriptions.remove(sub)

        return _unregister

    @property
    def needs_active_update(self) -> bool:
        """Determine if there are any subscriptions that require an active update."""
        return self._active_subscriptions is None or bool(self._active_subscriptions)


class OralbPassiveBluetoothDataProcessor(PassiveBluetoothDataProcessor):
    """PassiveBluetoothDataProcessor for Oralb integration."""

    coordinator: OralbActiveBluetoothProcessorCoordinator

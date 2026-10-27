"""The OKOK Scale integration."""

import logging

from okokscale.parser import OKOKScaleBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type OKOKScaleConfigEntry = ConfigEntry[ActiveBluetoothProcessorCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OKOKScaleConfigEntry) -> None:
    """Set up OKOK Scale device from a config entry."""
    address = entry.unique_id
    assert address is not None

    data = OKOKScaleBluetoothDeviceData()

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        return (
            hass.state is CoreState.running
            and data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll(service_info: BluetoothServiceInfoBleak) -> SensorUpdate:
        # BluetoothServiceInfoBleak is defined in HA, otherwise would just pass it
        # directly to the OKOK Scale code
        # Make sure the device we have is one that we can connect with
        # in case it's coming from a passive scanner
        if service_info.connectable:
            connectable_device = service_info.device
        elif device := async_ble_device_from_address(
            hass, service_info.device.address, True
        ):
            connectable_device = device
        else:
            # We have no bluetooth controller that is in range of
            # the device to poll it
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_connectable_device",
                translation_placeholders={"address": service_info.device.address},
            )

        return await data.async_poll(connectable_device, service_info.advertisement)

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=data.update,
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
        # We will take advertisements from non-connectable devices
        # since we will trade the BLEDevice for a connectable one
        # if we need to poll it
        connectable=False,
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())


async def async_unload_entry(hass: HomeAssistant, entry: OKOKScaleConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

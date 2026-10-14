"""Synthetic device models for shared-layer tests."""

import logging
from typing import override

from lorawan_connection import Device, DeviceCollection, DeviceDescriptor

from homeassistant.components.lorawan import LoRaWANEntity, device_identifier
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class ExampleDevice(Device):
    """Select synthetic catalog identities without a vendor decoder."""

    identifiers = {"example": (123, "sensor"), "other_stack": ("vendor", "sensor")}


class ExampleDevices(DeviceCollection[ExampleDevice]):
    """Limit the consumer to its supported model."""

    DEVICES = (ExampleDevice,)


DESCRIPTOR = DeviceDescriptor(
    network_id="network",
    dev_eui="0201010101010101",
    name="Greenhouse",
    application_id="application",
    profile_id="profile",
    stack="example",
    brand_id=123,
    model_id="sensor",
)


class ExampleCoordinator(DataUpdateCoordinator[ExampleDevice]):
    """Forward library notifications to HA entities."""

    def __init__(self, hass: HomeAssistant, device: ExampleDevice) -> None:
        """Observe one model."""
        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=None,
            name=device.descriptor.name,
        )
        self.async_set_updated_data(device)
        self._unsubscribe = device.add_update_listener(
            lambda: self.async_set_updated_data(device)
        )

    @override
    async def async_shutdown(self) -> None:
        self._unsubscribe()
        await super().async_shutdown()


class ExampleSensor(LoRaWANEntity[ExampleDevice], SensorEntity):
    """Exercise entity and registry lifecycle without a decoder."""

    def __init__(self, coordinator: ExampleCoordinator, key: str) -> None:
        """Bind a synthetic measurement to the coordinator."""
        super().__init__(coordinator)
        self._attr_name = key.capitalize()
        self._attr_unique_id = f"{coordinator.data.descriptor.network_id}:{coordinator.data.descriptor.dev_eui}:{key}"
        self._attr_device_info = {
            "identifiers": {device_identifier("test_vendor", coordinator.data)},
            "name": coordinator.data.descriptor.name,
        }

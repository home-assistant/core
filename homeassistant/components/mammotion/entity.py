"""Base class for entities."""

from typing import cast, override

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MammotionBaseUpdateCoordinator


class MammotionBaseEntity(CoordinatorEntity[MammotionBaseUpdateCoordinator]):
    """Representation of a Luba lawn mower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MammotionBaseUpdateCoordinator, key: str) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_name}_{key}"

    @override
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        mower = self.coordinator.api.mammotion.get_device_by_name(
            self.coordinator.device_name
        )

        swversion: str | None = None
        model_id: str | None = None
        connections: set[tuple[str, str]] = set()

        if mower is not None:
            swversion = mower.device_firmwares.device_version

            if mower.mower_state.model_id != "":
                model_id = mower.mower_state.model_id
            if (
                mower.mqtt_properties is not None
                and mower.mqtt_properties.params.items.extMod is not None
            ):
                model_id = cast(str, mower.mqtt_properties.params.items.extMod.value)

            if mower.mower_state.ble_mac != "":
                connections.add(
                    (
                        CONNECTION_BLUETOOTH,
                        format_mac(mower.mower_state.ble_mac),
                    )
                )

            if mower.mower_state.wifi_mac != "":
                connections.add(
                    (
                        CONNECTION_NETWORK_MAC,
                        format_mac(mower.mower_state.wifi_mac),
                    )
                )

        nick_name = self.coordinator.device.nick_name
        device_name = (
            self.coordinator.device_name
            if nick_name is None or nick_name == ""
            else self.coordinator.device.nick_name
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.device_name)},
            manufacturer="Mammotion",
            serial_number=self.coordinator.device_name.split("-", 1)[-1],
            model_id=model_id,
            name=device_name,
            sw_version=swversion,
            model=self.coordinator.device.product_model or model_id,
            suggested_area="Garden",
            connections=connections,
        )

    @override
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None and self.coordinator.is_online()

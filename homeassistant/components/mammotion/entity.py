"""Base class for entities."""

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT, DOMAIN
from .coordinator import MammotionBaseUpdateCoordinator


class MammotionBaseEntity(CoordinatorEntity[MammotionBaseUpdateCoordinator]):
    """Representation of a Luba lawn mower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MammotionBaseUpdateCoordinator, key: str) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_name}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        mower = self.coordinator.manager.get_device_by_name(
            self.coordinator.device_name
        )
        swversion = mower.state.device_firmwares.device_version

        model_id = None
        if mower is not None:
            if mower.state.mower_state.model_id != "":
                model_id = mower.state.mower_state.model_id
            if (
                mower.state.mqtt_properties is not None
                and mower.state.mqtt_properties.params.items.extMod is not None
            ):
                model_id = mower.state.mqtt_properties.params.items.extMod.value

        nick_name = self.coordinator.device.nickName
        device_name = (
            self.coordinator.device_name
            if nick_name is None or nick_name == ""
            else self.coordinator.device.nickName
        )

        connections: set[tuple[str, str]] = set()

        if mower.ble():
            connections.add(
                (
                    CONNECTION_BLUETOOTH,
                    format_mac(mower.ble().ble_device.address),
                )
            )

        if mower.state.mower_state.wifi_mac != "":
            connections.add(
                (
                    CONNECTION_NETWORK_MAC,
                    format_mac(mower.state.mower_state.wifi_mac),
                )
            )

        if mower.state.mower_state.ble_mac != "":
            connections.add(
                (
                    CONNECTION_BLUETOOTH,
                    format_mac(mower.state.mower_state.ble_mac),
                )
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.deviceName)},
            manufacturer="Mammotion",
            serial_number=self.coordinator.device_name.split("-", 1)[-1],
            model_id=model_id,
            name=device_name,
            sw_version=swversion,
            model=self.coordinator.device.productModel or model_id,
            suggested_area="Garden",
            connections=connections,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.data is not None
            and self.coordinator.update_failures
            <= self.coordinator.config_entry.options.get(
                CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
            )
        )

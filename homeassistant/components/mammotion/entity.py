"""Base class for entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACCOUNTNAME, CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT, DOMAIN
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
        mower = self.coordinator.data
        swversion = mower.device_firmwares.device_version

        product_key = mower.mower_state.product_key
        if product_key is None or product_key == "":
            if self.coordinator.manager.mqtt_list.get(
                self.coordinator.config_entry.data.get(CONF_ACCOUNTNAME)
            ):
                mammotion_cloud = self.coordinator.manager.mqtt_list.get(
                    self.coordinator.device_name
                )
                if mammotion_cloud is not None:
                    device_list = mammotion_cloud.cloud_client.devices_by_account_response.data.data
                    device = [
                        device
                        for device in device_list
                        if device.deviceName == self.coordinator.device.deviceName
                    ].pop()

                    mower.mower_state.product_key = device.productKey

        model_id = None
        if mower is not None:
            if mower.mower_state.model_id != "":
                model_id = mower.mower_state.model_id
            if mower.mqtt_properties is not None:
                model_id = mower.mqtt_properties.params.items.extMod.value

        nick_name = self.coordinator.device.nickName
        device_name = (
            self.coordinator.device_name
            if nick_name is None or nick_name == ""
            else self.coordinator.device.nickName
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

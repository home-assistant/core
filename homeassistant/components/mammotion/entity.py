"""Base class for entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pymammotion.utility.device_type import DeviceType

from . import DEFAULT_RETRY_COUNT
from .const import CONF_RETRY_COUNT, DOMAIN
from .coordinator import MammotionDataUpdateCoordinator


class MammotionBaseEntity(CoordinatorEntity[MammotionDataUpdateCoordinator]):
    """Representation of a Luba lawn mower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MammotionDataUpdateCoordinator, key: str) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_name}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        mower = self.coordinator.manager.mower(
                    self.coordinator.device_name
                )
        swversion = None
        if (
            len(
                mower.net.toapp_devinfo_resp.resp_ids
            )
            > 0
        ):
            swversion = (
                mower
                .net.toapp_devinfo_resp.resp_ids[0]
                .info
            )

        product_key = mower.net.toapp_wifi_iot_status.productkey
        if product_key is None or product_key == "":
            if self.coordinator.manager.cloud_client:
                device_list = self.coordinator.manager.cloud_client.get_devices_by_account_response().data.data
                device = next((device for device in device_list if device.deviceName == self.coordinator.device_name), None)
                product_key = device.productKey

        device_model = DeviceType.value_of_str(
                self.coordinator.device_name,
                product_key,
            ).get_model()

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_name)},
            manufacturer="Mammotion",
            serial_number=self.coordinator.device_name.split("-", 1)[-1],
            name=self.coordinator.device_name,
            sw_version=swversion,
            model=device_model,
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

"""Base class for entities."""

from pymammotion.utility.device_type import DeviceType

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_RETRY_COUNT, DOMAIN
from .coordinator import MammotionDataUpdateCoordinator


class MammotionBaseEntity(CoordinatorEntity[MammotionDataUpdateCoordinator]):
    """Representation of a Luba lawn mower."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MammotionDataUpdateCoordinator, key: str) -> None:
        """Initialize the lawn mower."""
        super().__init__(coordinator)
        swversion = "0.0.0"
        if (
            len(
                coordinator.devices.mower(
                    coordinator.device_name
                ).net.toapp_devinfo_resp.resp_ids
            )
            > 0
        ):
            swversion = (
                coordinator.devices.mower(coordinator.device_name)
                .net.toapp_devinfo_resp.resp_ids[0]
                .info
            )

        self._attr_unique_id = f"{coordinator.device_name}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_name)},
            manufacturer="Mammotion",
            serial_number=coordinator.device_name.split("-", 1)[-1],
            name=coordinator.device_name,
            sw_version=swversion,
            model=DeviceType.value_of_str(
                coordinator.device_name,
                coordinator.devices.mower(
                    coordinator.device_name
                ).net.toapp_wifi_iot_status.productkey,
            ).get_model(),
            suggested_area="Garden",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.data is not None
            and self.coordinator.update_failures
            <= self.coordinator.config_entry.options[CONF_RETRY_COUNT]
        )

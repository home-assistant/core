"""Parent class for every Overkiz device."""

from typing import cast, override

from pyoverkiz.enums import APIType, OverkizAttribute, OverkizCommandParam, OverkizState
from pyoverkiz.models import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OverkizDataUpdateCoordinator
from .executor import OverkizExecutor


class OverkizEntity(CoordinatorEntity[OverkizDataUpdateCoordinator]):
    """Representation of an Overkiz device entity."""

    _attr_has_entity_name = True
    _attr_name: str | None

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self.device_url = device_url
        self.executor = OverkizExecutor(device_url, coordinator)

        self._attr_assumed_state = not self.device.states
        self._attr_unique_id = self.device.device_url

        if self.device.identifier.is_sub_device:
            # In case of sub entity, use the provided label as name
            self._attr_name = self.device.label

        self._attr_device_info = self.generate_device_info()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.device.available:
            return super().available

        # Workaround: local API may incorrectly report
        # available=False (Somfy-TaHoma-Developer-Mode#217)
        if self.coordinator.client.server_config.api_type != APIType.LOCAL:
            return False

        if status_state := self.device.states.get(OverkizState.CORE_STATUS):
            return (
                status_state.value == OverkizCommandParam.AVAILABLE
                and super().available
            )

        return False

    @property
    def device(self) -> Device:
        """Return Overkiz device linked to this entity."""
        return self.coordinator.data[self.device_url]

    def generate_device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        # Some devices, such as the Smart Thermostat have several devices
        # in one physical device, with same device url, terminated by '#' and a number.
        # In this case, we use the base device url as the device identifier.
        if self.device.identifier.is_sub_device:
            # Only return the url of the base device, to inherit device name
            # and model from parent device.
            return DeviceInfo(
                identifiers={(DOMAIN, self.device.identifier.base_device_url)},
            )

        manufacturer = (
            self.device.attributes.get_value(OverkizAttribute.CORE_MANUFACTURER)
            or self.device.states.get_value(OverkizState.CORE_MANUFACTURER_NAME)
            or self.coordinator.client.server_config.manufacturer
        )

        model = (
            self.device.states.first_value(
                [
                    OverkizState.CORE_MODEL,
                    OverkizState.CORE_PRODUCT_MODEL_NAME,
                    OverkizState.IO_MODEL,
                ]
            )
            or self.device.ui_class.value
        )

        suggested_area = (
            self.coordinator.areas[self.device.place_oid]
            if self.coordinator.areas and self.device.place_oid
            else None
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self.device.identifier.base_device_url)},
            name=self.device.label,
            manufacturer=str(manufacturer),
            model=str(model),
            sw_version=cast(
                str,
                self.device.attributes.get_value(
                    OverkizAttribute.CORE_FIRMWARE_REVISION
                ),
            ),
            model_id=self.device.widget,
            hw_version=self.device.controllable_name,
            suggested_area=suggested_area,
            via_device=(DOMAIN, self.device.identifier.gateway_id),
            configuration_url=self.coordinator.client.server_config.configuration_url,
        )


class OverkizDescriptiveEntity(OverkizEntity):
    """Representation of a Overkiz device entity based on a description."""

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{self.entity_description.key}"

        if self.device.identifier.is_sub_device:
            if isinstance(description.name, str):
                self._attr_name = f"{self.device.label} {description.name}"
            else:
                self._attr_name = self.device.label
        elif isinstance(description.name, str):
            self._attr_name = description.name

"""Parent class for every Overkiz device."""

from __future__ import annotations

from typing import cast

from pyoverkiz.enums import OverkizAttribute, OverkizState
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
    _attr_name: str | None = None

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize the device."""
        super().__init__(coordinator)
        self.device_url = device_url
        split_device_url = self.device_url.split("#")
        self.base_device_url = split_device_url[0]
        if len(split_device_url) == 2:
            self.index_device_url = split_device_url[1]
        self.executor = OverkizExecutor(device_url, coordinator)

        self._attr_assumed_state = not self.device.states
        self._attr_unique_id = self.device.device_url

        if self.is_sub_device:
            # In case of sub entity, use the provided label as name
            self._attr_name = self.device.label

        self._attr_device_info = self.generate_device_info()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available and super().available

    @property
    def is_sub_device(self) -> bool:
        """Return True if device is a sub device."""
        return "#" in self.device_url and not self.device_url.endswith("#1")

    @property
    def device(self) -> Device:
        """Return Overkiz device linked to this entity."""
        return self.coordinator.data[self.device_url]

    def _get_sibling_devices(self) -> list[Device]:
        """Return sibling devices sharing the same base device URL."""
        prefix = f"{self.base_device_url}#"
        return [
            device
            for device in self.coordinator.data.values()
            if device.device_url != self.device_url
            and device.device_url.startswith(prefix)
        ]

    def _has_siblings_with_different_place_oid(self) -> bool:
        """Check if sibling devices have different placeOIDs.

        Returns True if siblings have different place_oid values, indicating
        devices should be grouped by placeOID rather than by base URL.
        """
        my_place_oid = self.device.place_oid
        if not my_place_oid:
            return False

        return any(
            sibling.place_oid and sibling.place_oid != my_place_oid
            for sibling in self._get_sibling_devices()
        )

    def _get_device_index(self, device_url: str) -> int | None:
        """Extract numeric index from device URL (e.g., 'io://gw/123#4' -> 4)."""
        suffix = device_url.split("#")[-1]
        return int(suffix) if suffix.isdigit() else None

    def _is_main_device_for_place_oid(self) -> bool:
        """Check if this device is the main device for its placeOID group.

        The device with the lowest URL index among siblings sharing the same
        placeOID is considered the main device and provides full device info.
        """
        my_place_oid = self.device.place_oid
        if not my_place_oid:
            return True

        my_index = self._get_device_index(self.device_url)
        if my_index is None:
            return True

        return not any(
            (sibling_index := self._get_device_index(sibling.device_url)) is not None
            and sibling_index < my_index
            for sibling in self._get_sibling_devices()
            if sibling.place_oid == my_place_oid
        )

    def _get_via_device_id(self, use_place_oid_grouping: bool) -> str:
        """Return the via_device identifier for device registry hierarchy.

        Sub-devices link to the main actuator (#1 device) when using placeOID
        grouping, otherwise they link directly to the gateway.
        """
        gateway_id = self.executor.get_gateway_id()

        if not use_place_oid_grouping or self.device_url.endswith("#1"):
            return gateway_id

        main_device = self.coordinator.data.get(f"{self.base_device_url}#1")
        if main_device and main_device.place_oid:
            return f"{self.base_device_url}#{main_device.place_oid}"

        return gateway_id

    def generate_device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        # Some devices, such as the Smart Thermostat, have several sub-devices
        # sharing the same base URL (terminated by '#' and a number).
        use_place_oid_grouping = self._has_siblings_with_different_place_oid()

        # Sub-devices without placeOID grouping inherit info from parent device
        if self.is_sub_device and not use_place_oid_grouping:
            return DeviceInfo(
                identifiers={(DOMAIN, self.executor.base_device_url)},
            )

        # Determine identifier based on grouping strategy
        if use_place_oid_grouping:
            identifier = f"{self.base_device_url}#{self.device.place_oid}"
            # Non-main devices only reference the identifier
            if not self._is_main_device_for_place_oid():
                return DeviceInfo(identifiers={(DOMAIN, identifier)})
        else:
            identifier = self.executor.base_device_url

        manufacturer = (
            self.executor.select_attribute(OverkizAttribute.CORE_MANUFACTURER)
            or self.executor.select_state(OverkizState.CORE_MANUFACTURER_NAME)
            or self.coordinator.client.server.manufacturer
        )

        model = (
            self.executor.select_state(
                OverkizState.CORE_MODEL,
                OverkizState.CORE_PRODUCT_MODEL_NAME,
                OverkizState.IO_MODEL,
            )
            or self.device.ui_class.value
        )

        suggested_area = (
            self.coordinator.areas[self.device.place_oid]
            if self.coordinator.areas and self.device.place_oid
            else None
        )

        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=self.device.label,
            manufacturer=str(manufacturer),
            model=str(model),
            sw_version=cast(
                str,
                self.executor.select_attribute(OverkizAttribute.CORE_FIRMWARE_REVISION),
            ),
            model_id=self.device.widget,
            hw_version=self.device.controllable_name,
            suggested_area=suggested_area,
            via_device=(DOMAIN, self._get_via_device_id(use_place_oid_grouping)),
            configuration_url=self.coordinator.client.server.configuration_url,
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

        if self.is_sub_device:
            # In case of sub device, use the provided label
            # and append the name of the type of entity
            self._attr_name = f"{self.device.label} {description.name}"
        elif isinstance(description.name, str):
            self._attr_name = description.name

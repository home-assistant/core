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

    def _has_siblings_with_different_place_oid(self) -> bool:
        """Check if sibling devices (same base_url) have different placeOIDs.

        Returns True if there are devices sharing the same base_device_url
        but with different place_oid values. This indicates the devices
        should be grouped by placeOID rather than by base URL.
        """
        if not self.device.place_oid:
            return False

        for device in self.coordinator.data.values():
            # Check for sibling devices (same base URL, different device URL)
            if (
                device.device_url != self.device_url
                and device.device_url.startswith(f"{self.base_device_url}#")
                and device.place_oid
                and device.place_oid != self.device.place_oid
            ):
                return True
        return False

    def _is_main_device_for_place_oid(self) -> bool:
        """Check if this device is the main device for its placeOID group.

        When multiple devices share the same placeOID, the one with the lowest
        device URL index is considered the main device and provides full device info.
        Other devices just reference the identifier.
        """
        if not self.device.place_oid:
            return True

        my_index = int(self.device_url.split("#")[-1])

        # Find all devices with the same base URL and placeOID
        for device in self.coordinator.data.values():
            if (
                device.device_url != self.device_url
                and device.device_url.startswith(f"{self.base_device_url}#")
                and device.place_oid == self.device.place_oid
            ):
                # Compare device URL indices - lower index is the main device
                other_index = int(device.device_url.split("#")[-1])
                if other_index < my_index:
                    return False
        return True

    def generate_device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        # Some devices, such as the Smart Thermostat have several devices
        # in one physical device, with same device url, terminated by '#' and a number.
        # In this case, we use the base device url as the device identifier.

        # Check if siblings have different placeOIDs - if so, use placeOID grouping
        use_place_oid_grouping = self._has_siblings_with_different_place_oid()

        if self.is_sub_device and not use_place_oid_grouping:
            # Only return the url of the base device, to inherit device name
            # and model from parent device.
            return DeviceInfo(
                identifiers={(DOMAIN, self.executor.base_device_url)},
            )

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
            or self.device.widget.value
        )

        suggested_area = (
            self.coordinator.areas[self.device.place_oid]
            if self.coordinator.areas and self.device.place_oid
            else None
        )

        # Use placeOID-based identifier when siblings have different placeOIDs
        if use_place_oid_grouping:
            identifier = f"{self.base_device_url}#{self.device.place_oid}"

            # Only the main device for this placeOID provides full device info.
            # Other devices just reference the identifier.
            if not self._is_main_device_for_place_oid():
                return DeviceInfo(
                    identifiers={(DOMAIN, identifier)},
                )

            # Link sub-devices to the main actuator (#1 device).
            main_device = self.coordinator.data.get(f"{self.base_device_url}#1")
            if main_device and main_device.place_oid:
                main_device_identifier = (
                    f"{self.base_device_url}#{main_device.place_oid}"
                )
                if self.device_url.endswith("#1"):
                    via_device = (DOMAIN, self.executor.get_gateway_id())
                else:
                    via_device = (DOMAIN, main_device_identifier)
            else:
                via_device = (DOMAIN, self.executor.get_gateway_id())
        else:
            identifier = self.executor.base_device_url
            via_device = (DOMAIN, self.executor.get_gateway_id())

        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=self.device.label,
            manufacturer=str(manufacturer),
            model=str(model),
            sw_version=cast(
                str,
                self.executor.select_attribute(OverkizAttribute.CORE_FIRMWARE_REVISION),
            ),
            hw_version=self.device.controllable_name,
            suggested_area=suggested_area,
            via_device=via_device,
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

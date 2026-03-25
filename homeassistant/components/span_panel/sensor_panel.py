"""Panel-level sensors for Span Panel integration."""

# pylint: disable=hass-enforce-class-module

from __future__ import annotations

import logging
from typing import Any

from span_panel_api import SpanBatterySnapshot, SpanPanelSnapshot

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import UNDEFINED

from .coordinator import SpanPanelCoordinator
from .helpers import (
    build_bess_unique_id_for_entry,
    construct_panel_unique_id_for_entry,
    construct_synthetic_unique_id_for_entry,
    get_panel_entity_suffix,
)
from .sensor_base import SpanEnergySensorBase, SpanSensorBase
from .sensor_definitions import (
    SpanBessMetadataSensorEntityDescription,
    SpanPanelBatterySensorEntityDescription,
    SpanPanelDataSensorEntityDescription,
    SpanPanelStatusSensorEntityDescription,
    SpanPVMetadataSensorEntityDescription,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


class SpanPanelPanelStatus(
    SpanSensorBase[SpanPanelDataSensorEntityDescription, SpanPanelSnapshot]
):
    """Span Panel data status sensor entity."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelDataSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize the Span Panel data status sensor."""
        super().__init__(data_coordinator, description, snapshot)

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate unique ID for panel data sensors."""
        return construct_panel_unique_id_for_entry(
            self.coordinator, snapshot, description.key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate friendly name for panel data sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "Sensor"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanPanelSnapshot:
        """Get the data source for the panel data status sensor."""
        return snapshot


class SpanPanelStatus(
    SpanSensorBase[SpanPanelStatusSensorEntityDescription, SpanPanelSnapshot]
):
    """Span Panel hardware status sensor entity."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelStatusSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize the Span Panel hardware status sensor."""
        super().__init__(data_coordinator, description, snapshot)

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelStatusSensorEntityDescription,
    ) -> str:
        """Generate unique ID for panel status sensors."""
        return construct_panel_unique_id_for_entry(
            self.coordinator, snapshot, description.key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelStatusSensorEntityDescription,
    ) -> str:
        """Generate friendly name for panel status sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "Status"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanPanelSnapshot:
        """Get the data source for the panel status sensor."""
        return snapshot

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes for the software version sensor."""
        if not self.coordinator.data:
            return None

        snapshot = self.coordinator.data
        attributes: dict[str, Any] = {}

        attributes["panel_size"] = snapshot.panel_size
        if snapshot.wifi_ssid is not None:
            attributes["wifi_ssid"] = snapshot.wifi_ssid

        return attributes or None


class SpanPanelBattery(
    SpanSensorBase[SpanPanelBatterySensorEntityDescription, SpanBatterySnapshot]
):
    """Span Panel battery sensor entity."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelBatterySensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        device_info_override: DeviceInfo | None = None,
    ) -> None:
        """Initialize the Span Panel battery sensor."""
        super().__init__(data_coordinator, description, snapshot)

        if device_info_override is not None:
            self._attr_device_info = device_info_override

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelBatterySensorEntityDescription,
    ) -> str:
        """Generate unique ID for battery sensors."""
        return construct_panel_unique_id_for_entry(
            self.coordinator, snapshot, description.key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelBatterySensorEntityDescription,
    ) -> str:
        """Generate friendly name for battery sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "Battery"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanBatterySnapshot:
        """Get the data source for the battery sensor."""
        return snapshot.battery


class SpanPanelPowerSensor(
    SpanSensorBase[SpanPanelDataSensorEntityDescription, SpanPanelSnapshot]
):
    """Panel power sensor with calculated amperage attribute."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelDataSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        device_info_override: DeviceInfo | None = None,
    ) -> None:
        """Initialize the enhanced panel power sensor."""
        self._description_key = description.key
        super().__init__(data_coordinator, description, snapshot)

        if device_info_override is not None:
            self._attr_device_info = device_info_override

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate unique ID for panel power sensors."""
        entity_suffix = get_panel_entity_suffix(description.key)
        return construct_synthetic_unique_id_for_entry(
            self.coordinator, snapshot, entity_suffix, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate friendly name for panel power sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "Power"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanPanelSnapshot:
        """Get the data source for the panel power sensor."""
        return snapshot

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes including amperage calculation."""
        if not self.coordinator.data:
            return None

        attributes: dict[str, Any] = {}

        # Add voltage attribute (standard panel voltage)
        attributes["voltage"] = 240

        # Calculate amperage from power (P = V * I, so I = P / V)
        if self.native_value is not None and isinstance(self.native_value, int | float):
            try:
                amperage = float(self.native_value) / 240.0
                attributes["amperage"] = round(amperage, 2)
            except ValueError, ZeroDivisionError:
                attributes["amperage"] = 0.0
        else:
            attributes["amperage"] = 0.0

        return attributes


class SpanPanelEnergySensor(
    SpanEnergySensorBase[SpanPanelDataSensorEntityDescription, SpanPanelSnapshot]
):
    """Panel energy sensor with grace period tracking."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPanelDataSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize the panel energy sensor."""
        super().__init__(data_coordinator, description, snapshot)

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate unique ID for panel energy sensors."""
        entity_suffix = get_panel_entity_suffix(description.key)
        return construct_synthetic_unique_id_for_entry(
            self.coordinator, snapshot, entity_suffix, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPanelDataSensorEntityDescription,
    ) -> str:
        """Generate friendly name for panel energy sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "Energy"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanPanelSnapshot:
        """Get the data source for the panel energy sensor."""
        return snapshot

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes including grace period and voltage."""
        # Get base grace period attributes
        base_attributes = super().extra_state_attributes or {}
        attributes = dict(base_attributes)

        # Add voltage attribute (standard panel voltage)
        attributes["voltage"] = 240

        return attributes or None


class SpanBessMetadataSensor(
    SpanSensorBase[SpanBessMetadataSensorEntityDescription, SpanBatterySnapshot]
):
    """BESS metadata sensor entity on the BESS sub-device."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanBessMetadataSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        device_info_override: DeviceInfo,
    ) -> None:
        """Initialize the BESS metadata sensor."""
        super().__init__(data_coordinator, description, snapshot)
        self._attr_device_info = device_info_override

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanBessMetadataSensorEntityDescription,
    ) -> str:
        """Generate unique ID for BESS metadata sensors."""
        return build_bess_unique_id_for_entry(
            self.coordinator, snapshot, description.key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanBessMetadataSensorEntityDescription,
    ) -> str:
        """Generate friendly name for BESS metadata sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "BESS Sensor"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanBatterySnapshot:
        """Get the data source for the BESS metadata sensor."""
        return snapshot.battery


class SpanPVMetadataSensor(
    SpanSensorBase[SpanPVMetadataSensorEntityDescription, SpanPanelSnapshot]
):
    """PV metadata sensor entity on the main panel device."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanPVMetadataSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
    ) -> None:
        """Initialize the PV metadata sensor."""
        super().__init__(data_coordinator, description, snapshot)

    def _generate_unique_id(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPVMetadataSensorEntityDescription,
    ) -> str:
        """Generate unique ID for PV metadata sensors."""
        return construct_panel_unique_id_for_entry(
            self.coordinator, snapshot, description.key, self._device_name
        )

    def _generate_friendly_name(
        self,
        snapshot: SpanPanelSnapshot,
        description: SpanPVMetadataSensorEntityDescription,
    ) -> str:
        """Generate friendly name for PV metadata sensors."""
        if description.name is not None and description.name is not UNDEFINED:
            return str(description.name)
        return "PV Sensor"

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanPanelSnapshot:
        """Get the data source for the PV metadata sensor."""
        return snapshot

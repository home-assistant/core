"""Base entity for Span Panel integration."""

from __future__ import annotations

from span_panel_api import SpanPanelSnapshot

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME
from .coordinator import SpanPanelCoordinator
from .util import snapshot_to_device_info


class SpanPanelEntity(CoordinatorEntity[SpanPanelCoordinator]):
    """Base entity for all Span Panel platforms."""

    _attr_has_entity_name = True

    @staticmethod
    def _build_device_info(
        coordinator: SpanPanelCoordinator,
        snapshot: SpanPanelSnapshot,
    ) -> DeviceInfo:
        """Construct device info from coordinator and snapshot."""
        device_name = coordinator.config_entry.data.get(
            CONF_DEVICE_NAME, coordinator.config_entry.title
        )
        host = coordinator.config_entry.data.get(CONF_HOST)
        return snapshot_to_device_info(snapshot, device_name, host=host)

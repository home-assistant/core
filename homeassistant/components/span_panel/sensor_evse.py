"""EVSE (EV Charger) sensors for Span Panel integration."""

# pylint: disable=hass-enforce-class-module

from __future__ import annotations

import logging

from span_panel_api import SpanEvseSnapshot, SpanPanelSnapshot

from .const import CONF_DEVICE_NAME, USE_CIRCUIT_NUMBERS
from .coordinator import SpanPanelCoordinator
from .helpers import build_evse_unique_id_for_entry, resolve_evse_display_suffix
from .sensor_base import SpanSensorBase
from .sensor_definitions import SpanEvseSensorEntityDescription
from .util import evse_device_info

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Fallback EVSE snapshot used when the EVSE disappears mid-session
_EMPTY_EVSE = SpanEvseSnapshot(node_id="", feed_circuit_id="")


class SpanEvseSensor(SpanSensorBase[SpanEvseSensorEntityDescription, SpanEvseSnapshot]):
    """EVSE (EV charger) sensor entity."""

    def __init__(
        self,
        data_coordinator: SpanPanelCoordinator,
        description: SpanEvseSensorEntityDescription,
        snapshot: SpanPanelSnapshot,
        evse_id: str,
    ) -> None:
        """Initialize the EVSE sensor."""
        self._evse_id = evse_id
        super().__init__(data_coordinator, description, snapshot)

        # Override device_info to point to EVSE sub-device instead of panel
        panel_name = (
            data_coordinator.config_entry.data.get(
                CONF_DEVICE_NAME, data_coordinator.config_entry.title
            )
            or "Span Panel"
        )
        panel_identifier = snapshot.serial_number

        evse = snapshot.evse.get(evse_id, _EMPTY_EVSE)
        use_circuit_numbers = data_coordinator.config_entry.options.get(
            USE_CIRCUIT_NUMBERS, False
        )
        display_suffix = resolve_evse_display_suffix(
            evse, snapshot, use_circuit_numbers
        )
        self._attr_device_info = evse_device_info(
            panel_identifier, evse, panel_name, display_suffix
        )

    def _generate_unique_id(
        self, snapshot: SpanPanelSnapshot, description: SpanEvseSensorEntityDescription
    ) -> str:
        """Generate unique ID for EVSE sensors."""
        return build_evse_unique_id_for_entry(
            self.coordinator,
            snapshot,
            self._evse_id,
            description.key,
            self._device_name,
        )

    def _generate_friendly_name(
        self, snapshot: SpanPanelSnapshot, description: SpanEvseSensorEntityDescription
    ) -> str:
        """Generate friendly name for EVSE sensors."""
        return str(description.name)

    def get_data_source(self, snapshot: SpanPanelSnapshot) -> SpanEvseSnapshot:
        """Get the EVSE snapshot for this sensor's charger."""
        return snapshot.evse.get(self._evse_id, _EMPTY_EVSE)

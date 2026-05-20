"""Wibeee sensor platform for Home Assistant.

Creates sensor entities for each phase and sensor type detected on the
Wibeee energy monitor device. All sensors are ``CoordinatorEntity``
instances backed by a single ``WibeeeCoordinator``:

- **Polling mode**: Coordinator periodically fetches status.xml.
- **Push mode**: Coordinator receives data via ``async_push_update()``.

Entity creation strategy:
    Phases are **discovered** from the initial data fetch (hardware-dependent).
    For each discovered phase, entities are created only for ``SENSOR_TYPES``
    whose keys are present in the initial phase data.

Documentation: https://github.com/fquinto/pywibeee
"""

from __future__ import annotations

import logging

from pywibeee import WibeeeDeviceInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WibeeeConfigEntry
from .const import (
    CONF_UPDATE_MODE,
    DOMAIN,
    KNOWN_MODELS,
    MODE_LOCAL_PUSH,
    PUSH_REFRESHABLE_SENSOR_KEYS,
    SENSOR_TYPES,
    WibeeeSensorEntityDescription,
)
from .coordinator import WibeeeCoordinator

_LOGGER = logging.getLogger(__name__)


PARALLEL_UPDATES = 0

# Map phase names to human-readable labels
PHASE_NAMES: dict[str, str] = {
    "fase1": "L1",
    "fase2": "L2",
    "fase3": "L3",
    "fase4": "Total",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WibeeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wibeee sensor entities from a config entry."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    device_info = runtime.device_info

    # Discover phases from initial data (hardware-dependent).
    # Single-phase: fase1 + fase4. Three-phase: fase1-3 + fase4.
    data = coordinator.data
    if data is None:
        _LOGGER.warning(
            "No data available for Wibeee %s (%s); no sensors created",
            device_info.mac_addr_short,
            device_info.ip_addr,
        )
        return

    # Filter to known phases only
    discovered_phases = [p for p in data if p in PHASE_NAMES]
    if not discovered_phases:
        _LOGGER.warning(
            "No phases found for Wibeee %s (%s)",
            device_info.mac_addr_short,
            device_info.ip_addr,
        )
        return

    # Build entities: discovered phases x sensor types present in data.
    # In push mode, restrict to keys the push parser can refresh; otherwise
    # any extra sensor (THD, angle, capacitive-reactive, ...) would become
    # unavailable as soon as the first push update arrives.
    is_push_mode = (
        entry.options.get(CONF_UPDATE_MODE, MODE_LOCAL_PUSH) == MODE_LOCAL_PUSH
    )
    eligible_sensor_types: dict[str, WibeeeSensorEntityDescription] = (
        {k: v for k, v in SENSOR_TYPES.items() if k in PUSH_REFRESHABLE_SENSOR_KEYS}
        if is_push_mode
        else SENSOR_TYPES
    )

    # Process fase4 (Total) first to ensure the parent device exists
    sorted_phases = sorted(
        discovered_phases,
        key=lambda p: (0 if p == "fase4" else 1, p),
    )
    entities: list[WibeeeSensor] = [
        WibeeeSensor(
            coordinator=coordinator,
            device_info=device_info,
            phase_key=phase_key,
            description=description,
        )
        for phase_key in sorted_phases
        if isinstance(data.get(phase_key), dict)
        for sensor_key, description in eligible_sensor_types.items()
        if sensor_key in data[phase_key]
    ]

    async_add_entities(entities)
    _LOGGER.debug(
        "Added %d sensors for Wibeee %s (%s) across %d phases",
        len(entities),
        device_info.mac_addr_short,
        device_info.ip_addr,
        len(sorted_phases),
    )


# ---------------------------------------------------------------------------
# Device info builder
# ---------------------------------------------------------------------------


def _build_device_info(device_info: WibeeeDeviceInfo, phase_key: str) -> dr.DeviceInfo:
    """Build HA DeviceInfo for a sensor entity."""
    model_name = KNOWN_MODELS.get(device_info.model, f"Wibeee {device_info.model}")
    is_phase = phase_key in ("fase1", "fase2", "fase3")
    phase_label = PHASE_NAMES.get(phase_key, phase_key)

    if is_phase:
        return dr.DeviceInfo(
            identifiers={(DOMAIN, f"{device_info.mac_addr_formatted}_{phase_key}")},
            via_device=(DOMAIN, device_info.mac_addr_formatted),
            name=f"Wibeee {device_info.mac_addr_short} {phase_label}",
            model=f"{model_name} Clamp",
            manufacturer="Smilics",
        )
    return dr.DeviceInfo(
        identifiers={(DOMAIN, device_info.mac_addr_formatted)},
        name=f"Wibeee {device_info.mac_addr_short}",
        model=model_name,
        manufacturer="Smilics",
        sw_version=device_info.firmware_version,
        configuration_url=f"http://{device_info.ip_addr}/",
    )


# ---------------------------------------------------------------------------
# Unified sensor entity (polling + push)
# ---------------------------------------------------------------------------


class WibeeeSensor(CoordinatorEntity[WibeeeCoordinator], SensorEntity):
    """Wibeee sensor entity backed by a coordinator.

    Works for both polling and push modes. The coordinator provides
    the data; the sensor reads its specific phase/key from it.
    """

    _attr_has_entity_name = True
    entity_description: WibeeeSensorEntityDescription

    def __init__(
        self,
        coordinator: WibeeeCoordinator,
        device_info: WibeeeDeviceInfo,
        phase_key: str,
        description: WibeeeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._phase_key = phase_key
        self.entity_description = description

        self._attr_unique_id = (
            f"{device_info.mac_addr_formatted}_{phase_key}_{description.key}"
        )
        self._attr_translation_key = description.translation_key
        self._attr_device_info = _build_device_info(device_info, phase_key)

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        phase_data = data.get(self._phase_key)
        if not isinstance(phase_data, dict):
            return None
        value = phase_data.get(self.entity_description.key)
        if value is None:
            return None
        try:
            return float(value)
        except ValueError, TypeError:
            return None

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data for this sensor.

        Extends CoordinatorEntity.available (which checks coordinator
        connectivity) with phase/key-level granularity and value validation.
        """
        if not super().available:
            return False
        data = self.coordinator.data
        if not isinstance(data, dict):
            return False
        phase_data = data.get(self._phase_key)
        if not isinstance(phase_data, dict):
            return False
        value = phase_data.get(self.entity_description.key)
        if value is None:
            return False
        try:
            float(value)
        except ValueError, TypeError:
            return False
        return True

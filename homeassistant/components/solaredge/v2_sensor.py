"""Native V2 entities: preserve equivalent identities, distinguish changed data."""

from typing import override

from aiosolaredge.monitoring import INVENTORY

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .v2_runtime import PERIODS, SolarEdgeV2Coordinator

ENERGY = SensorEntityDescription(
    key="lifetime_energy",
    translation_key="lifetime_energy",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
)
POWER = SensorEntityDescription(
    key="average_power",
    translation_key="average_power",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
)
SUPPORTED = {"lifetime_energy", "site_details", *INVENTORY, *PERIODS}


class SolarEdgeV2Sensor(CoordinatorEntity[SolarEdgeV2Coordinator], SensorEntity):
    """Do not relabel instantaneous recorder history with interval averages."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarEdgeV2Coordinator,
        description: SensorEntityDescription,
        unsupported: bool = False,
        serial: str | None = None,
    ) -> None:
        """Retain original native identities and descriptions."""
        super().__init__(coordinator)
        self.entity_description = description
        self.unsupported = unsupported
        self.serial = serial
        self.reading_key = f"{serial}_{description.key}" if serial else description.key
        self._attr_unique_id = (
            coordinator.site_id
            if description.key == "site_details"
            else f"{coordinator.site_id}_{self.reading_key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.site_id}_{serial}"
                    if serial
                    else coordinator.site_id,
                )
            },
            manufacturer="SolarEdge",
        )
        if serial:
            self._attr_device_info.update(
                {"name": f"Battery {serial}", "serial_number": serial}
            )

    @property
    @override
    def available(self) -> bool:
        """Unsupported current readings stay unavailable, not fabricated zero."""
        if self.serial and not any(
            device["serialNumber"] == self.serial and device.get("active", True)
            for device in (self.coordinator.state["inventory"] or {}).get(
                "batteries", []
            )
        ):
            return False
        return not self.unsupported and super().available

    @property
    @override
    def native_value(self) -> float | str | None:
        """Expose actual nullable readings or bounded metadata."""
        if self.unsupported:
            return None
        key = self.entity_description.key
        if key == "site_details":
            if (
                self.coordinator.state.get("permissions", {}).get("metadata")
                == "denied"
            ):
                return None
            status = self.coordinator.state["metadata"].get("activationStatus")
            return status.lower() if isinstance(status, str) else None
        if key in INVENTORY:
            inventory = self.coordinator.state["inventory"]
            return len(inventory[key]) if inventory is not None else None
        reading = (self.coordinator.data or {}).get(self.reading_key)
        return reading.value if reading else None

    @property
    @override
    def extra_state_attributes(self) -> dict:
        """Differentiate range-end boundaries from source sample timestamps."""
        key = self.entity_description.key
        if self.unsupported:
            return {
                "v2_status": "no_equivalent_basic_reading",
                "history_preserved": True,
            }
        if key == "site_details":
            names = {
                "name": "name",
                "peakPower": "peak_power",
                "installationDate": "installation_date",
                "lastUpdateTime": "last_update_time",
            }
            return {
                new: self.coordinator.state["metadata"][old]
                for old, new in names.items()
                if old in self.coordinator.state["metadata"]
            }
        if key in INVENTORY:
            inventory = self.coordinator.state["inventory"]
            return {key: inventory[key]} if inventory is not None else {}
        reading = (self.coordinator.data or {}).get(self.reading_key)
        if key in PERIODS and not key.startswith("storage_"):
            return {
                "range_end": reading.timestamp.isoformat() if reading else None,
                "range_start": self.coordinator.state["periods"].get(self.reading_key),
                "timestamp_semantics": "requested_range_not_source_sample",
            }
        return {
            "sample_timestamp": reading.timestamp.isoformat()
            if reading and reading.value is not None
            else None,
            "resolution": "QUARTER_HOUR"
            if key == "average_power"
            else "onboard_counter_delta"
            if "charge_energy" in key
            else "onboard_counter",
            "api_mode": "basic_v2",
        }

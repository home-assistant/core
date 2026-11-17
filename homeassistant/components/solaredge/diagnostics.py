"""Diagnostics support for SolarEdge."""

from typing import Any

from homeassistant.const import CONF_API_KEY, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DATA_MODULES_COORDINATOR, DATA_SERVICES
from .coordinator import (
    SolarEdgeDataService,
    SolarEdgeDetailsDataService,
    SolarEdgeEnergyDetailsService,
    SolarEdgeInventoryDataService,
    SolarEdgeOverviewDataService,
    SolarEdgePowerFlowDataService,
    SolarEdgeStorageDataService,
)
from .types import SolarEdgeConfigEntry

TO_OMIT = {
    "connectedInverterSn",
    "connectedSolaredgeDeviceSN",
    "serialNumber",
    "SN",
}

SERVICE_NAMES: dict[type[SolarEdgeDataService], str] = {
    SolarEdgeDetailsDataService: "details",
    SolarEdgeOverviewDataService: "overview",
    SolarEdgeInventoryDataService: "inventory",
    SolarEdgePowerFlowDataService: "power_flow",
    SolarEdgeEnergyDetailsService: "energy_details",
    SolarEdgeStorageDataService: "storage",
}

BATTERY_KEY_SUFFIXES = ("state_of_charge", "power", "charge_energy", "discharge_energy")


def _storage_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return storage data with per-battery keys grouped instead of keyed by serial."""
    serials = [
        key.removesuffix("_state_of_charge")
        for key in data
        if key.endswith("_state_of_charge")
    ]
    return {
        "charge_energy": data.get("charge_energy"),
        "discharge_energy": data.get("discharge_energy"),
        "batteries": [
            {suffix: data.get(f"{serial}_{suffix}") for suffix in BATTERY_KEY_SUFFIXES}
            for serial in serials
        ],
    }


def _service_diagnostics(service: SolarEdgeDataService) -> dict[str, Any]:
    """Return diagnostics for a data service."""
    if isinstance(service, SolarEdgeStorageDataService):
        data = _storage_data(service.data)
    else:
        data = service.data
    attributes = service.attributes
    if isinstance(service, SolarEdgeDetailsDataService):
        # Site name is user defined
        attributes = {k: v for k, v in attributes.items() if k != "name"}
    elif isinstance(service, SolarEdgeInventoryDataService):
        # Attributes are nested as {category: {category: [devices]}}
        attributes = {
            category: [
                {k: v for k, v in device.items() if k not in TO_OMIT}
                for device in value[category]
            ]
            for category, value in attributes.items()
        }
    return {
        "last_update_success": service.coordinator.last_update_success,
        "data": data,
        "attributes": attributes,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolarEdgeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    diagnostics: dict[str, Any] = {
        "api_key_configured": CONF_API_KEY in entry.data,
        "web_login_configured": CONF_USERNAME in entry.data,
        "services": {
            SERVICE_NAMES[type(service)]: _service_diagnostics(service)
            for service in runtime_data.get(DATA_SERVICES, [])
        },
    }
    if modules_coordinator := runtime_data.get(DATA_MODULES_COORDINATOR):
        diagnostics["modules_last_update_success"] = (
            modules_coordinator.last_update_success
        )
    return diagnostics

"""Diagnostics support for Enphase Envoy."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from attr import asdict
from pyenphase import EnvoyData
from pyenphase.const import SupportedFeatures

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

CONF_TITLE = "title"

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_TOKEN,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if TYPE_CHECKING:
        assert coordinator.envoy.data
    Envoy_Data: EnvoyData = coordinator.envoy.data

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices = []
    # for each device associated with the envoy get entity and state information
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entities = []
        for entity in er.async_entries_for_device(
            entity_registry, device_id=device.id, include_disabled_entities=True
        ):
            state_dict = None
            if state := hass.states.get(entity.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)
            entities.append({"entity": asdict(entity), "state": state_dict})
        devices.append({"device": asdict(device), "entities": entities})

    # redact envoy serial in entity data
    device_entities = json.loads(
        json.dumps(devices).replace(coordinator.envoy_serial_number, "<<envoyserial>>")
    )

    # redact envoy serial in envoy data
    cleaned_data = json.loads(
        json.dumps(coordinator.data).replace(
            coordinator.envoy_serial_number, "<<envoyserial>>"
        )
    )

    envoy_data: dict[str, Any] = {
        "encharge_inventory": Envoy_Data.encharge_inventory,
        "encharge_power": Envoy_Data.encharge_power,
        "encharge_aggregate": Envoy_Data.encharge_aggregate,
        "enpower": Envoy_Data.enpower,
        "system_consumption": Envoy_Data.system_consumption,
        "system_production": Envoy_Data.system_production,
        "system_consumption_phases": Envoy_Data.system_consumption_phases,
        "system_production_phases": Envoy_Data.system_production_phases,
        "ctmeter_production": Envoy_Data.ctmeter_production,
        "ctmeter_consumption": Envoy_Data.ctmeter_consumption,
        "ctmeter_production_phases": Envoy_Data.ctmeter_production_phases,
        "ctmeter_consumption_phases": Envoy_Data.ctmeter_consumption_phases,
        "dry_contact_status": Envoy_Data.dry_contact_status,
        "dry_contact_settings": Envoy_Data.dry_contact_settings,
        "inverters": Envoy_Data.inverters,
        "tariff": Envoy_Data.tariff,
    }

    envoy_properties: dict[str, Any] = {
        "envoy_firmware": coordinator.envoy.firmware,
        "part_number": coordinator.envoy.part_number,
        "envoy_model": coordinator.envoy.envoy_model,
        "supported_features": [
            feature.name
            for feature in SupportedFeatures
            if feature in coordinator.envoy.supported_features
        ],
        "phase_mode": coordinator.envoy.phase_mode,
        "phase_count": coordinator.envoy.phase_count,
        "active_phasecount": coordinator.envoy.active_phase_count,
        "ct_count": coordinator.envoy.ct_meter_count,
        "ct_consumption_meter": coordinator.envoy.consumption_meter_type,
        "ct_production_meter": coordinator.envoy.production_meter_type,
    }

    diagnostic_data: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "envoy_properties": envoy_properties,
        "data": cleaned_data,
        "envoy_entities_by_device": device_entities,
        "EnvoyData": envoy_data,
    }

    return diagnostic_data

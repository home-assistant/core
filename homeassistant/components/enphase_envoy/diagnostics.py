"""Diagnostics support for Enphase Envoy."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from attr import asdict
from pyenphase.envoy import Envoy
from pyenphase.exceptions import EnvoyError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

from .const import OPTION_DIAGNOSTICS_INCLUDE_FIXTURES
from .coordinator import EnphaseConfigEntry

CONF_TITLE = "title"
CLEAN_TEXT = "<<envoyserial>>"

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_TOKEN,
}


async def _get_fixture_collection(envoy: Envoy, serial: str) -> dict[str, Any]:
    """Collect Envoy endpoints to use for test fixture set."""
    fixture_data: dict[str, Any] = {}
    end_points = [
        "/info",
        "/api/v1/production",
        "/api/v1/production/inverters",
        "/production.json",
        "/production.json?details=1",
        "/production",
        "/ivp/ensemble/power",
        "/ivp/ensemble/inventory",
        "/ivp/ensemble/dry_contacts",
        "/ivp/ensemble/status",
        "/ivp/ensemble/secctrl",
        "/ivp/ss/dry_contact_settings",
        "/admin/lib/tariff",
        "/ivp/ss/gen_config",
        "/ivp/ss/gen_schedule",
        "/ivp/sc/pvlimit",
        "/ivp/ss/pel_settings",
        "/ivp/ensemble/generator",
        "/ivp/meters",
        "/ivp/meters/readings",
    ]

    for end_point in end_points:
        try:
            response = await envoy.request(end_point)
            fixture_data[end_point] = response.text.replace("\n", "").replace(
                serial, CLEAN_TEXT
            )
            fixture_data[f"{end_point}_log"] = json_dumps(
                {
                    "headers": dict(response.headers.items()),
                    "code": response.status_code,
                }
            )
        except EnvoyError as err:
            fixture_data[f"{end_point}_log"] = {"Error": repr(err)}
    return fixture_data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    if TYPE_CHECKING:
        assert coordinator.envoy.data
    envoy_data = coordinator.envoy.data
    envoy = coordinator.envoy

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_entities = []
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
            entity_dict = asdict(entity)
            entity_dict.pop("_cache", None)
            entities.append({"entity": entity_dict, "state": state_dict})
        device_dict = asdict(device)
        device_dict.pop("_cache", None)
        device_entities.append({"device": device_dict, "entities": entities})

    # remove envoy serial
    old_serial = coordinator.envoy_serial_number

    coordinator_data = copy.deepcopy(coordinator.data)
    coordinator_data_cleaned = json_dumps(coordinator_data).replace(
        old_serial, CLEAN_TEXT
    )

    device_entities_cleaned = json_dumps(device_entities).replace(
        old_serial, CLEAN_TEXT
    )

    envoy_model: dict[str, Any] = {
        "encharge_inventory": envoy_data.encharge_inventory,
        "encharge_power": envoy_data.encharge_power,
        "encharge_aggregate": envoy_data.encharge_aggregate,
        "enpower": envoy_data.enpower,
        "system_consumption": envoy_data.system_consumption,
        "system_production": envoy_data.system_production,
        "system_consumption_phases": envoy_data.system_consumption_phases,
        "system_production_phases": envoy_data.system_production_phases,
        "ctmeter_production": envoy_data.ctmeter_production,
        "ctmeter_consumption": envoy_data.ctmeter_consumption,
        "ctmeter_storage": envoy_data.ctmeter_storage,
        "ctmeter_production_phases": envoy_data.ctmeter_production_phases,
        "ctmeter_consumption_phases": envoy_data.ctmeter_consumption_phases,
        "ctmeter_storage_phases": envoy_data.ctmeter_storage_phases,
        "dry_contact_status": envoy_data.dry_contact_status,
        "dry_contact_settings": envoy_data.dry_contact_settings,
        "inverters": envoy_data.inverters,
        "tariff": envoy_data.tariff,
    }

    envoy_properties: dict[str, Any] = {
        "envoy_firmware": envoy.firmware,
        "part_number": envoy.part_number,
        "envoy_model": envoy.envoy_model,
        "supported_features": [feature.name for feature in envoy.supported_features],
        "phase_mode": envoy.phase_mode,
        "phase_count": envoy.phase_count,
        "active_phasecount": envoy.active_phase_count,
        "ct_count": envoy.ct_meter_count,
        "ct_consumption_meter": envoy.consumption_meter_type,
        "ct_production_meter": envoy.production_meter_type,
        "ct_storage_meter": envoy.storage_meter_type,
    }

    fixture_data: dict[str, Any] = {}
    if entry.options.get(OPTION_DIAGNOSTICS_INCLUDE_FIXTURES, False):
        fixture_data = await _get_fixture_collection(envoy=envoy, serial=old_serial)

    diagnostic_data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "envoy_properties": envoy_properties,
        "raw_data": json_loads(coordinator_data_cleaned),
        "envoy_model_data": envoy_model,
        "envoy_entities_by_device": json_loads(device_entities_cleaned),
        "fixtures": fixture_data,
    }

    return diagnostic_data

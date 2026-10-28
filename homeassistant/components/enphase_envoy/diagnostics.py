"""Diagnostics support for Enphase Envoy."""

import copy
from datetime import datetime
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from pyenphase.envoy import Envoy
from pyenphase.exceptions import EnvoyClientClosedError, EnvoyError

from homeassistant.components.diagnostics import (
    async_redact_data,
    device_entry_as_dict,
    entity_entry_as_dict,
)
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


async def _get_fixture_collection(
    envoy: Envoy, mask: bool, strict: bool
) -> dict[str, Any]:
    try:
        fixtures: dict[str, Any] = await envoy.fixture_collection(
            mask_serials=mask, strict_masking=strict
        )
        # pyenphase may leak Clientconnectionerror header data in endpoint_log, clean until fixed
        for ep in [ep for ep in fixtures if ep.endswith("_log") and ep.startswith("/")]:
            if (
                "error" in (ep_data := fixtures[ep])
                and "ClientResponseError" in ep_data["error"]
            ):
                ep_data["error"] = "ClientResponseError"
    except ClientError as err:
        return {
            "collection_aborted_log": f"Error: {type(err).__name__ if not hasattr(err, 'status') else err.status}"
        }
    except (EnvoyError, EnvoyClientClosedError) as err:
        return {"collection_aborted_log": f"Error: {err!r}"}
    return fixtures


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
            entity_dict = entity_entry_as_dict(entity)
            entities.append({"entity": entity_dict, "state": state_dict})
        device_dict = device_entry_as_dict(device)
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
        "acb_power": envoy_data.acb_power,
        "acb_inventory": envoy_data.acb_inventory,
        "battery_aggregate": envoy_data.battery_aggregate,
        "collar": envoy_data.collar,
        "c6cc": envoy_data.c6cc,
        "system_consumption": envoy_data.system_consumption,
        "system_production": envoy_data.system_production,
        "system_consumption_phases": envoy_data.system_consumption_phases,
        "system_production_phases": envoy_data.system_production_phases,
        "ctmeters": envoy_data.ctmeters,
        "ctmeters_phases": envoy_data.ctmeters_phases,
        "dry_contact_status": envoy_data.dry_contact_status,
        "dry_contact_settings": envoy_data.dry_contact_settings,
        "inverters": envoy_data.inverters,
        "tariff": envoy_data.tariff,
    }
    # Add Envoy active interface information to report
    active_interface: dict[str, Any] = {}
    if coordinator.interface:
        active_interface = {
            "name": (interface := coordinator.interface).primary_interface,
            "interface type": interface.interface_type,
            "mac": interface.mac,
            "uses dhcp": interface.dhcp,
            "firmware build date": datetime.fromtimestamp(
                interface.software_build_epoch
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "envoy timezone": interface.timezone,
        }

    envoy_properties: dict[str, Any] = {
        "envoy_firmware": envoy.firmware,
        "part_number": envoy.part_number,
        "envoy_model": envoy.envoy_model,
        "active interface": active_interface,
        "token_lifetime": coordinator.token_lifetime,
        "supported_features": [feature.name for feature in envoy.supported_features],
        "phase_mode": envoy.phase_mode,
        "phase_count": envoy.phase_count,
        "active_phasecount": envoy.active_phase_count,
        "ct_count": envoy.ct_meter_count,
        "ct_consumption_meter": envoy.consumption_meter_type,
        "ct_production_meter": envoy.production_meter_type,
        "ct_storage_meter": envoy.storage_meter_type,
        "ct_meters": list(envoy_data.ctmeters.keys()),
    }

    fixture_data: dict[str, Any] = {}
    if entry.options.get(OPTION_DIAGNOSTICS_INCLUDE_FIXTURES, False):
        # use strict masking until option_flow let user select mode that should be used
        fixture_data = await _get_fixture_collection(
            envoy=envoy, mask=True, strict=True
        )

    diagnostic_data: dict[str, Any] = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "envoy_properties": envoy_properties,
        "raw_data": json_loads(coordinator_data_cleaned),
        "envoy_model_data": envoy_model,
        "envoy_entities_by_device": json_loads(device_entities_cleaned),
        "fixtures": fixture_data,
    }

    return diagnostic_data

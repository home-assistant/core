"""The test for the sensibo entity."""

from __future__ import annotations

from unittest.mock import patch

from pysensibo.model import SensiboData
import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.sensibo.const import SENSIBO_ERRORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    load_int: ConfigEntry,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo climate."""

    state1 = hass.states.get("climate.hallway")
    assert state1

    dr_entries = dr.async_entries_for_config_entry(device_registry, load_int.entry_id)
    dr_entry: dr.DeviceEntry
    for dr_entry in dr_entries:
        if dr_entry.name == "Hallway":
            assert dr_entry.identifiers == {("sensibo", "ABC999111")}
            device_id = dr_entry.id

    er_entries = er.async_entries_for_device(
        entity_registry, device_id, include_disabled_entities=True
    )
    er_entry: er.RegistryEntry
    for er_entry in er_entries:
        if er_entry.name == "Hallway":
            assert er_entry.unique_id == "Hallway"


@pytest.mark.parametrize("p_error", SENSIBO_ERRORS)
async def test_entity_failed_service_calls(
    hass: HomeAssistant,
    p_error: Exception,
    load_int: ConfigEntry,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo send command with error."""

    state = hass.states.get("climate.hallway")
    assert state

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        return_value={"result": {"status": "Success"}},
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
            side_effect=p_error,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
            blocking=True,
        )

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"

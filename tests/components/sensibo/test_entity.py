"""The test for the sensibo entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pysensibo.model import SensiboData
import pytest

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.number.const import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.sensibo.const import SENSIBO_ERRORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_entity(
    hass: HomeAssistant, load_int: ConfigEntry, get_data: SensiboData
) -> None:
    """Test the Sensibo climate."""

    state1 = hass.states.get("climate.hallway")
    assert state1

    dr_reg = dr.async_get(hass)
    dr_entries = dr.async_entries_for_config_entry(dr_reg, load_int.entry_id)
    dr_entry: dr.DeviceEntry
    for dr_entry in dr_entries:
        if dr_entry.name == "Hallway":
            assert dr_entry.identifiers == {("sensibo", "ABC999111")}
            device_id = dr_entry.id

    er_reg = er.async_get(hass)
    er_entries = er.async_entries_for_device(
        er_reg, device_id, include_disabled_entities=True
    )
    er_entry: er.RegistryEntry
    for er_entry in er_entries:
        if er_entry.name == "Hallway":
            assert er_entry.unique_id == "Hallway"


@pytest.mark.parametrize("p_error", SENSIBO_ERRORS)
async def test_entity_send_command(
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

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
        side_effect=p_error,
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {ATTR_ENTITY_ID: state.entity_id, ATTR_FAN_MODE: "low"},
                blocking=True,
            )

    state = hass.states.get("climate.hallway")
    assert state.attributes["fan_mode"] == "low"


async def test_entity_send_command_calibration(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    load_int: ConfigEntry,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo send command for calibration."""

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.1"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_calibration",
        return_value={"status": "success"},
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: 0.2},
            blocking=True,
        )

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.2"

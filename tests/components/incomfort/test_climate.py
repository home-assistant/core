"""Climate sensor tests for Intergas InComfort integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import climate
from homeassistant.components.incomfort.coordinator import InComfortData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_HEATER_STATUS, MOCK_HEATER_STATUS_HEATING

from tests.common import snapshot_platform


@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.CLIMATE])
@pytest.mark.parametrize(
    "mock_room_status",
    [
        {"room_temp": 21.42, "setpoint": 18.0, "override": 19.0},
        {"room_temp": 21.42, "setpoint": 18.0, "override": 0.0},
    ],
    ids=["override", "zero_override"],
)
@pytest.mark.parametrize(
    "mock_entry_options",
    [None, {"legacy_setpoint_status": True}],
    ids=["modern", "legacy"],
)
async def test_setup_platform(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort entities are set up correctly.

    Thermostats report 0.0 as override if no override is set
    or when the setpoint has been changed manually,
    Some older thermostats do not reset the override setpoint has been changed manually.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_heater_status", "hvac_action"),
    [
        (MOCK_HEATER_STATUS.copy(), climate.HVACAction.IDLE),
        (MOCK_HEATER_STATUS_HEATING.copy(), climate.HVACAction.HEATING),
    ],
    ids=["idle", "heating"],
)
async def test_hvac_state(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    mock_config_entry: ConfigEntry,
    hvac_action: climate.HVACAction,
) -> None:
    """Test the HVAC state of the thermostat."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("climate.thermostat_1")
    assert state is not None
    assert state.attributes["hvac_action"] is hvac_action


async def test_target_temp(
    hass: HomeAssistant, mock_incomfort: MagicMock, mock_config_entry: ConfigEntry
) -> None:
    """Test changing the target temperature."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("climate.thermostat_1")
    assert state is not None

    incomfort_data: InComfortData = mock_config_entry.runtime_data.incomfort_data

    with patch.object(
        incomfort_data.heaters[0].rooms[0], "set_override", AsyncMock()
    ) as mock_set_override:
        await hass.services.async_call(
            climate.DOMAIN,
            climate.SERVICE_SET_TEMPERATURE,
            service_data={
                ATTR_ENTITY_ID: "climate.thermostat_1",
                ATTR_TEMPERATURE: 19.0,
            },
        )
    mock_set_override.assert_called_once_with(19.0)

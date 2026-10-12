"""Tests for the Plugwise water_heater platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

HA_PLUGWISE_SMILE_ASYNC_UPDATE = (
    "homeassistant.components.plugwise.coordinator.Smile.async_update"
)


@pytest.mark.usefixtures("mock_smile_adam_jip")
@pytest.mark.parametrize("platforms", [(WATER_HEATER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_water_heater_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam water_heater snapshot with dhw_state off."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_water_heater_setpoint_change(
    hass: HomeAssistant,
    mock_smile_adam_jip: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test Adam water_heater setpoint-change."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.opentherm_domestic_hot_water",
            ATTR_TEMPERATURE: 55,
        },
        blocking=True,
    )
    assert mock_smile_adam_jip.set_number.call_count == 1
    mock_smile_adam_jip.set_number.assert_called_with(
        "e4684553153b44afbef2200885f379dc",
        "dhw_temperature",
        55.0,
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.opentherm_domestic_hot_water",
                ATTR_TEMPERATURE: 65,
            },
            blocking=True,
        )
    assert mock_smile_adam_jip.set_number.call_count == 1

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.opentherm_domestic_hot_water",
                ATTR_TEMPERATURE: 15,
            },
            blocking=True,
        )
    assert mock_smile_adam_jip.set_number.call_count == 1


@pytest.mark.usefixtures("mock_smile_anna")
@pytest.mark.parametrize("chosen_env", ["anna_loria_cooling_active"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
@pytest.mark.parametrize("platforms", [(WATER_HEATER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_water_heater_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna water_heater snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_water_heater_states(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Anna water_heater states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("water_heater.opentherm_domestic_hot_water"))
    assert state.state == STATE_OFF

    data = mock_smile_anna.async_update.return_value
    data["1cbf783bb11e4a7c8a6843dee3a86927"]["binary_sensors"]["dhw_state"] = True
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (state := hass.states.get("water_heater.opentherm_domestic_hot_water"))
        assert state.state == STATE_HEAT_PUMP

    data = mock_smile_anna.async_update.return_value
    data["1cbf783bb11e4a7c8a6843dee3a86927"]["binary_sensors"][
        "secondary_boiler_state"
    ] = True
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (state := hass.states.get("water_heater.opentherm_domestic_hot_water"))
        assert state.state == STATE_GAS


async def test_adam_water_heater_active_state(
    hass: HomeAssistant,
    mock_smile_adam_jip: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Adam water_heater active state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    data = mock_smile_adam_jip.async_update.return_value
    data["e4684553153b44afbef2200885f379dc"]["binary_sensors"]["dhw_state"] = True
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (state := hass.states.get("water_heater.opentherm_domestic_hot_water"))
        assert state.state == STATE_GAS


@pytest.mark.usefixtures("mock_smile_adam_jip")
async def test_adam_water_heater_setpoint_error_uses_configured_unit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test out-of-range setpoint errors use the configured temperature unit."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.opentherm_domestic_hot_water",
                ATTR_TEMPERATURE: 145,
            },
            blocking=True,
        )

    assert exc_info.value.translation_placeholders == {
        "temperature": "62.77777777777778",
        "max_temp": "140.0",
        "min_temp": "104.0",
        "temperature_unit": "°F",
    }

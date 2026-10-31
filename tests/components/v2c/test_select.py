"""Test the V2C select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytrydan.models.trydan import ChargeMode, DynamicPowerMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.v2c.const import CONF_PV_AVAILABLE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the select entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.evse_1_1_1_1_charge_mode",
            ATTR_OPTION: "mixed",
        },
        blocking=True,
    )

    mock_v2c_client.charge_mode.assert_awaited_once_with(ChargeMode.MIXED)


async def test_select_not_created_when_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing charge mode entity is not created."""
    mock_v2c_client.get_data.return_value.charge_mode = None

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    entity_id = "select.evse_1_1_1_1_charge_mode"
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("option", "mode"),
    [
        ("profile", DynamicPowerMode.TIMED_POWER_ENABLED),
        ("pv_minimum", DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED),
        ("pv_exclusive", DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED),
        ("pv_grid", DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED),
        ("stop", DynamicPowerMode.TIMED_POWER_DISABLED_AND_STOP_MODE_SETTED),
    ],
)
async def test_dynamic_power_mode(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    option: str,
    mode: DynamicPowerMode,
) -> None:
    """Test changing the dynamic power mode without changing the power."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PV_AVAILABLE: True}
    )
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("select.evse_1_1_1_1_dynamic_power_mode")
    assert state is not None
    assert state.state == "pv_minimum"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.evse_1_1_1_1_dynamic_power_mode",
            ATTR_OPTION: option,
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(mode)
    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.parametrize(
    ("pv_available", "mode"),
    [(False, DynamicPowerMode.TIMED_POWER_ENABLED), (True, None)],
)
async def test_dynamic_power_mode_not_created(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pv_available: bool,
    mode: DynamicPowerMode | None,
) -> None:
    """Test the mode entity requires PV and a supported device."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PV_AVAILABLE: pv_available}
    )
    mock_v2c_client.get_data.return_value.dynamic_power_mode = mode
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("select.evse_1_1_1_1_dynamic_power_mode") is None

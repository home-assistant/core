"""Test Enphase Envoy number sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=["mock_envoy"],
)
async def test_no_number(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number platform entities are not created."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_number_operation(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy number entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.data.enpower.serial_number
    test_entity = f"{Platform.NUMBER}.enpower_{sn}_reserve_battery_level"

    assert (entity_state := hass.states.get(test_entity))
    assert mock_envoy.data.tariff.storage_settings.reserved_soc == float(
        entity_state.state
    )
    test_value = 30.0
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: test_entity,
            "value": test_value,
        },
        blocking=True,
    )

    mock_envoy.set_reserve_soc.assert_awaited_once_with(test_value)

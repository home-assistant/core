"""Test Enphase Envoy number sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    ("mock_envoy"),
    ["envoy_metered_batt_relay", "envoy_eu_batt"],
    indirect=["mock_envoy"],
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
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
async def test_number_operation_storage(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: bool,
) -> None:
    """Test enphase_envoy number storage entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.NUMBER}.{use_serial}_reserve_battery_level"

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
            ATTR_VALUE: test_value,
        },
        blocking=True,
    )

    mock_envoy.set_reserve_soc.assert_awaited_once_with(test_value)


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_number_operation_relays(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test enphase_envoy number relay entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.NUMBER}."

    for counter, (contact_id, dry_contact) in enumerate(
        mock_envoy.data.dry_contact_settings.items()
    ):
        name = dry_contact.load_name.lower().replace(" ", "_")
        test_entity = f"{entity_base}{name}_cutoff_battery_level"
        assert (entity_state := hass.states.get(test_entity))
        assert mock_envoy.data.dry_contact_settings[contact_id].soc_low == float(
            entity_state.state
        )
        test_value = 10.0 + counter
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_VALUE: test_value,
            },
            blocking=True,
        )

        mock_envoy.update_dry_contact.assert_awaited_once_with(
            {"id": contact_id, "soc_low": test_value}
        )
        mock_envoy.update_dry_contact.reset_mock()

        test_entity = f"{entity_base}{name}_restore_battery_level"
        assert (entity_state := hass.states.get(test_entity))
        assert mock_envoy.data.dry_contact_settings[contact_id].soc_high == float(
            entity_state.state
        )
        test_value = 80.0 - counter
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_VALUE: test_value,
            },
            blocking=True,
        )

        mock_envoy.update_dry_contact.assert_awaited_once_with(
            {"id": contact_id, "soc_high": test_value}
        )
        mock_envoy.update_dry_contact.reset_mock()

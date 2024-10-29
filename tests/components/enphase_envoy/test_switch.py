"""Test Enphase Envoy switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
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
async def test_switch(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SWITCH]):
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
async def test_no_switch(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch platform entities are not created."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_switch_grid_operation(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test switch platform operation for grid switches."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry)

    sn = mock_envoy.data.enpower.serial_number
    test_entity = f"{Platform.SWITCH}.enpower_{sn}_grid_enabled"

    # validate envoy value is reflected in entity
    assert (entity_state := hass.states.get(test_entity))
    assert entity_state.state == STATE_ON

    # test grid status switch operation
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.go_off_grid.assert_awaited_once_with()
    mock_envoy.go_off_grid.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.go_on_grid.assert_awaited_once_with()
    mock_envoy.go_on_grid.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.go_off_grid.assert_awaited_once_with()
    mock_envoy.go_off_grid.reset_mock()


@pytest.mark.parametrize(
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
async def test_switch_charge_from_grid_operation(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: str,
) -> None:
    """Test switch platform operation for charge from grid switches."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.SWITCH}.{use_serial}_charge_from_grid"

    # validate envoy value is reflected in entity
    assert (entity_state := hass.states.get(test_entity))
    assert entity_state.state == STATE_ON

    # test grid status switch operation
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.disable_charge_from_grid.assert_awaited_once_with()
    mock_envoy.disable_charge_from_grid.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.enable_charge_from_grid.assert_awaited_once_with()
    mock_envoy.enable_charge_from_grid.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: test_entity},
        blocking=True,
    )
    mock_envoy.disable_charge_from_grid.assert_awaited_once_with()
    mock_envoy.disable_charge_from_grid.reset_mock()


@pytest.mark.parametrize(
    ("mock_envoy", "entity_states"),
    [
        (
            "envoy_metered_batt_relay",
            {
                "NC1": (STATE_OFF, 0, 1),
                "NC2": (STATE_ON, 1, 0),
                "NC3": (STATE_OFF, 0, 1),
            },
        )
    ],
    indirect=["mock_envoy"],
)
async def test_switch_relay_operation(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_states: dict[str, tuple[str, int, int]],
) -> None:
    """Test enphase_envoy switch relay entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SWITCH}."

    for contact_id, dry_contact in mock_envoy.data.dry_contact_settings.items():
        name = dry_contact.load_name.lower().replace(" ", "_")
        test_entity = f"{entity_base}{name}"
        assert (entity_state := hass.states.get(test_entity))
        assert entity_state.state == entity_states[contact_id][0]
        open_count = entity_states[contact_id][1]
        close_count = entity_states[contact_id][2]

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: test_entity},
            blocking=True,
        )

        mock_envoy.open_dry_contact.assert_awaited_once_with(contact_id)
        mock_envoy.close_dry_contact.assert_not_awaited()
        mock_envoy.open_dry_contact.reset_mock()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: test_entity},
            blocking=True,
        )

        mock_envoy.close_dry_contact.assert_awaited_once_with(contact_id)
        mock_envoy.open_dry_contact.assert_not_awaited()
        mock_envoy.close_dry_contact.reset_mock()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: test_entity},
            blocking=True,
        )

        assert mock_envoy.open_dry_contact.await_count == open_count
        assert mock_envoy.close_dry_contact.await_count == close_count
        mock_envoy.open_dry_contact.reset_mock()
        mock_envoy.close_dry_contact.reset_mock()

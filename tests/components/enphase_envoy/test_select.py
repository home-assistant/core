"""Test Enphase Envoy select."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.select import (
    ACTION_OPTIONS,
    MODE_OPTIONS,
    RELAY_ACTION_MAP,
    RELAY_MODE_MAP,
    REVERSE_RELAY_ACTION_MAP,
    REVERSE_RELAY_MODE_MAP,
    REVERSE_STORAGE_MODE_MAP,
    STORAGE_MODE_MAP,
    STORAGE_MODE_OPTIONS,
)
from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION
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
async def test_select(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
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
async def test_no_select(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_select_relay_actions(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test select platform entities dry contact relay actions."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SELECT}."

    for contact_id, dry_contact in mock_envoy.data.dry_contact_settings.items():
        name = dry_contact.load_name.lower().replace(" ", "_")
        for target in (
            ("generator_action", dry_contact.generator_action, "generator_action"),
            ("microgrid_action", dry_contact.micro_grid_action, "micro_grid_action"),
            ("grid_action", dry_contact.grid_action, "grid_action"),
        ):
            test_entity = f"{entity_base}{name}_{target[0]}"
            assert (entity_state := hass.states.get(test_entity))
            assert RELAY_ACTION_MAP[target[1]] == (current_state := entity_state.state)
            # set all relay modes except current mode
            for action in [action for action in ACTION_OPTIONS if not current_state]:
                await hass.services.async_call(
                    SELECT_DOMAIN,
                    SERVICE_SELECT_OPTION,
                    {
                        ATTR_ENTITY_ID: test_entity,
                        ATTR_OPTION: action,
                    },
                    blocking=True,
                )
                mock_envoy.update_dry_contact.assert_called_once_with(
                    {"id": contact_id, target[2]: REVERSE_RELAY_ACTION_MAP[action]}
                )
                mock_envoy.update_dry_contact.reset_mock()
            # and finally back to original
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: test_entity,
                    ATTR_OPTION: current_state,
                },
                blocking=True,
            )
            mock_envoy.update_dry_contact.assert_called_once_with(
                {"id": contact_id, target[2]: REVERSE_RELAY_ACTION_MAP[current_state]}
            )
            mock_envoy.update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("mock_envoy"), ["envoy_metered_batt_relay"], indirect=["mock_envoy"]
)
async def test_select_relay_modes(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test select platform dry contact relay mode changes."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SELECT}."

    for contact_id, dry_contact in mock_envoy.data.dry_contact_settings.items():
        name = dry_contact.load_name.lower().replace(" ", "_")
        test_entity = f"{entity_base}{name}_mode"
        assert (entity_state := hass.states.get(test_entity))
        assert RELAY_MODE_MAP[dry_contact.mode] == (current_state := entity_state.state)
        for mode in [mode for mode in MODE_OPTIONS if not current_state]:
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: test_entity,
                    ATTR_OPTION: mode,
                },
                blocking=True,
            )
            mock_envoy.update_dry_contact.assert_called_once_with(
                {"id": contact_id, "mode": REVERSE_RELAY_MODE_MAP[mode]}
            )
            mock_envoy.update_dry_contact.reset_mock()

        # and finally current mode again
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_OPTION: current_state,
            },
            blocking=True,
        )
        mock_envoy.update_dry_contact.assert_called_once_with(
            {"id": contact_id, "mode": REVERSE_RELAY_MODE_MAP[current_state]}
        )
        mock_envoy.update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
async def test_select_storage_modes(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: str,
) -> None:
    """Test select platform entities storage mode changes."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.SELECT}.{use_serial}_storage_mode"

    assert (entity_state := hass.states.get(test_entity))
    assert STORAGE_MODE_MAP[mock_envoy.data.tariff.storage_settings.mode] == (
        current_state := entity_state.state
    )

    for mode in [mode for mode in STORAGE_MODE_OPTIONS if not current_state]:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )
        mock_envoy.set_storage_mode.assert_called_once_with(
            REVERSE_STORAGE_MODE_MAP[mode]
        )
        mock_envoy.set_storage_mode.reset_mock()

    # and finally with original mode
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: test_entity,
            ATTR_OPTION: current_state,
        },
        blocking=True,
    )
    mock_envoy.set_storage_mode.assert_called_once_with(
        REVERSE_STORAGE_MODE_MAP[current_state]
    )

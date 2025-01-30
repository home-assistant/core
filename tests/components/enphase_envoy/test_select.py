"""Test Enphase Envoy select."""

from unittest.mock import AsyncMock, patch

from pyenphase.exceptions import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.select import (
    RELAY_ACTION_MAP,
    RELAY_MODE_MAP,
    REVERSE_RELAY_ACTION_MAP,
    REVERSE_RELAY_MODE_MAP,
    REVERSE_STORAGE_MODE_MAP,
    STORAGE_MODE_MAP,
)
from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_envoy",
    ["envoy_metered_batt_relay", "envoy_eu_batt"],
    indirect=True,
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
    "mock_envoy",
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=True,
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


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
@pytest.mark.parametrize(
    ("relay", "target", "expected_state", "call_parameter"),
    [
        ("NC1", "generator_action", "shed", "generator_action"),
        ("NC1", "microgrid_action", "shed", "micro_grid_action"),
        ("NC1", "grid_action", "shed", "grid_action"),
        ("NC2", "generator_action", "shed", "generator_action"),
        ("NC2", "microgrid_action", "shed", "micro_grid_action"),
        ("NC2", "grid_action", "apply", "grid_action"),
        ("NC3", "generator_action", "apply", "generator_action"),
        ("NC3", "microgrid_action", "apply", "micro_grid_action"),
        ("NC3", "grid_action", "shed", "grid_action"),
    ],
)
@pytest.mark.parametrize("action", ["powered", "not_powered", "schedule", "none"])
async def test_select_relay_actions(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    target: str,
    expected_state: str,
    call_parameter: str,
    relay: str,
    action: str,
) -> None:
    """Test select platform entities dry contact relay actions."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SELECT}."

    assert (dry_contact := mock_envoy.data.dry_contact_settings[relay])
    assert (name := dry_contact.load_name.lower().replace(" ", "_"))

    test_entity = f"{entity_base}{name}_{target}"

    assert (entity_state := hass.states.get(test_entity))
    assert entity_state.state == RELAY_ACTION_MAP[expected_state]

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
        {"id": relay, call_parameter: REVERSE_RELAY_ACTION_MAP[action]}
    )


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
@pytest.mark.parametrize("relay_mode", ["battery", "standard"])
@pytest.mark.parametrize("relay", ["NC1", "NC2", "NC3"])
async def test_select_relay_modes(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    relay_mode: str,
    relay: str,
) -> None:
    """Test select platform dry contact relay mode changes."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SELECT}."

    assert (dry_contact := mock_envoy.data.dry_contact_settings[relay])
    assert (name := dry_contact.load_name.lower().replace(" ", "_"))

    test_entity = f"{entity_base}{name}_mode"

    assert (entity_state := hass.states.get(test_entity))
    assert entity_state.state == RELAY_MODE_MAP[dry_contact.mode]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: test_entity,
            ATTR_OPTION: relay_mode,
        },
        blocking=True,
    )
    mock_envoy.update_dry_contact.assert_called_once_with(
        {"id": relay, "mode": REVERSE_RELAY_MODE_MAP[relay_mode]}
    )


@pytest.mark.parametrize(
    ("mock_envoy", "relay", "target", "action"),
    [("envoy_metered_batt_relay", "NC1", "generator_action", "powered")],
    indirect=["mock_envoy"],
)
async def test_update_dry_contact_actions_with_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    target: str,
    relay: str,
    action: str,
) -> None:
    """Test select platform update dry contact action with error return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    entity_base = f"{Platform.SELECT}."

    assert (dry_contact := mock_envoy.data.dry_contact_settings[relay])
    assert (name := dry_contact.load_name.lower().replace(" ", "_"))

    test_entity = f"{entity_base}{name}_{target}"

    mock_envoy.update_dry_contact.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match=f"Failed to execute async_select_option for {test_entity}, host",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_OPTION: action,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.parametrize(("mode"), ["backup", "self_consumption", "savings"])
async def test_select_storage_modes(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: str,
    mode: str,
) -> None:
    """Test select platform entities storage mode changes."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.SELECT}.{use_serial}_storage_mode"

    assert (entity_state := hass.states.get(test_entity))
    assert (
        entity_state.state
        == STORAGE_MODE_MAP[mock_envoy.data.tariff.storage_settings.mode]
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: test_entity,
            ATTR_OPTION: mode,
        },
        blocking=True,
    )
    mock_envoy.set_storage_mode.assert_called_once_with(REVERSE_STORAGE_MODE_MAP[mode])


@pytest.mark.parametrize(
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.parametrize(("mode"), ["backup"])
async def test_set_storage_modes_with_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: str,
    mode: str,
) -> None:
    """Test select platform set storage mode with error return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.SELECT}.{use_serial}_storage_mode"

    mock_envoy.set_storage_mode.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match=f"Failed to execute async_select_option for {test_entity}, host",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_OPTION: mode,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("mock_envoy", "use_serial"),
    [
        ("envoy_metered_batt_relay", "enpower_654321"),
        ("envoy_eu_batt", "envoy_1234"),
    ],
    indirect=["mock_envoy"],
)
async def test_select_storage_modes_if_none(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: str,
) -> None:
    """Test select platform entity storage mode when tariff storage_mode is none."""
    mock_envoy.data.tariff.storage_settings.mode = None
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.SELECT}.{use_serial}_storage_mode"

    assert (entity_state := hass.states.get(test_entity))
    assert entity_state.state == "unknown"

"""Test Enphase Envoy number sensors."""

from unittest.mock import AsyncMock, patch

from pyenphase.exceptions import EnvoyError
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
    "mock_envoy",
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
    ],
    indirect=True,
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
    ("mock_envoy", "use_serial", "expected_value", "test_value"),
    [
        ("envoy_metered_batt_relay", "enpower_654321", 15.0, 30.0),
        ("envoy_eu_batt", "envoy_1234", 0.0, 80.0),
    ],
    indirect=["mock_envoy"],
)
async def test_number_operation_storage(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: bool,
    expected_value: float,
    test_value: float,
) -> None:
    """Test enphase_envoy number storage entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    test_entity = f"{Platform.NUMBER}.{use_serial}_reserve_battery_level"

    assert (entity_state := hass.states.get(test_entity))
    assert float(entity_state.state) == expected_value

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
    ("mock_envoy", "use_serial", "target", "test_value"),
    [
        ("envoy_metered_batt_relay", "enpower_654321", "reserve_battery_level", 30.0),
    ],
    indirect=["mock_envoy"],
)
async def test_number_operation_storage_with_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    use_serial: bool,
    target: str,
    test_value: float,
) -> None:
    """Test enphase_envoy number storage entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    test_entity = f"number.{use_serial}_{target}"

    mock_envoy.set_reserve_soc.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match=f"Failed to execute async_set_native_value for {test_entity}, host",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_VALUE: test_value,
            },
            blocking=True,
        )


@pytest.mark.parametrize("mock_envoy", ["envoy_metered_batt_relay"], indirect=True)
@pytest.mark.parametrize(
    ("relay", "target", "expected_value", "test_value", "test_field"),
    [
        ("NC1", "cutoff_battery_level", 25.0, 15.0, "soc_low"),
        ("NC1", "restore_battery_level", 70.0, 75.0, "soc_high"),
        ("NC2", "cutoff_battery_level", 30.0, 25.0, "soc_low"),
        ("NC2", "restore_battery_level", 70.0, 80.0, "soc_high"),
        ("NC3", "cutoff_battery_level", 30.0, 45.0, "soc_low"),
        ("NC3", "restore_battery_level", 70.0, 90.0, "soc_high"),
    ],
)
async def test_number_operation_relays(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    relay: str,
    target: str,
    expected_value: float,
    test_value: float,
    test_field: str,
) -> None:
    """Test enphase_envoy number relay entities operation."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    assert (dry_contact := mock_envoy.data.dry_contact_settings[relay])
    assert (name := dry_contact.load_name.lower().replace(" ", "_"))

    test_entity = f"number.{name}_{target}"

    assert (entity_state := hass.states.get(test_entity))
    assert float(entity_state.state) == expected_value

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
        {"id": relay, test_field: int(test_value)}
    )


@pytest.mark.parametrize(
    ("mock_envoy", "relay", "target", "test_value"),
    [
        ("envoy_metered_batt_relay", "NC1", "cutoff_battery_level", 15.0),
    ],
    indirect=["mock_envoy"],
)
async def test_number_operation_relays_with_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    relay: str,
    target: str,
    test_value: float,
) -> None:
    """Test enphase_envoy number relay entities operation with error returned."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry)

    assert (dry_contact := mock_envoy.data.dry_contact_settings[relay])
    assert (name := dry_contact.load_name.lower().replace(" ", "_"))

    test_entity = f"number.{name}_{target}"

    mock_envoy.update_dry_contact.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match=f"Failed to execute async_set_native_value for {test_entity}, host",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: test_entity,
                ATTR_VALUE: test_value,
            },
            blocking=True,
        )

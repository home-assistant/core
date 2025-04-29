"""Tests for Renault selects."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from renault_api.kamereon import schemas
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import check_entities_unavailable
from .const import MOCK_VEHICLES

from tests.common import load_fixture

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_selects(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault selects."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures("fixtures_with_no_data")
async def test_select_empty(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault selects with empty data from Renault."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures("fixtures_with_invalid_upstream_exception")
async def test_select_errors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault selects with temporary failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]

    expected_entities = mock_vehicle[Platform.SELECT]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_unavailable(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_select_access_denied(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault selects with access denied failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_select_not_supported(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault selects with access denied failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_select_charge_mode(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {
        ATTR_ENTITY_ID: "select.reg_number_charge_mode",
        ATTR_OPTION: "always",
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_mode",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_mode.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            SELECT_DOMAIN, SERVICE_SELECT_OPTION, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ("always",)

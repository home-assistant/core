"""Tests for the Fumis number entities."""

from unittest.mock import MagicMock

from fumis import FumisConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fumis.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import UNIQUE_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize(
    "init_integration", [Platform.NUMBER], indirect=True
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_power_level(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test setting the power level."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.clou_duo_power_level", ATTR_VALUE: 3},
        blocking=True,
    )

    mock_fumis.set_power.assert_called_once_with(3)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_set_fan_speed(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test setting the fan speed."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.clou_duo_fan_speed", ATTR_VALUE: 2},
        blocking=True,
    )

    mock_fumis.set_fan_speed.assert_called_once_with(2)


@pytest.mark.usefixtures("init_integration")
async def test_number_error_handling(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test error handling for number actions."""
    mock_fumis.set_power.side_effect = FumisConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.clou_duo_power_level", ATTR_VALUE: 3},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"


@pytest.mark.parametrize(
    "unique_id",
    [
        f"{UNIQUE_ID}_fan_speed",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_numbers_disabled_by_default(
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> None:
    """Test number entities that are disabled by default."""
    entry = entity_registry.async_get_entity_id("number", "fumis", unique_id)
    assert entry is not None, f"Entity with unique_id {unique_id} not found"
    assert (entity_entry := entity_registry.async_get(entry))
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_numbers_conditional_creation(
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fan_speed number is not created when data is missing."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_ids = {entry.unique_id for entry in entity_entries}

    # Fan speed should NOT exist with the minimal fixture
    assert f"{UNIQUE_ID}_fan_speed" not in unique_ids

    # Power level should still exist
    assert f"{UNIQUE_ID}_power_level" in unique_ids

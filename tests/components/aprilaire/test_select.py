"""Tests for the Aprilaire select platform."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SELECT]


pytestmark = [
    pytest.mark.usefixtures("mock_aprilaire"),
]


def _get_entity_id(
    entity_registry: er.EntityRegistry, unique_id_suffix: str
) -> str:
    """Get entity_id from the entity registry by unique_id suffix."""
    entry = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, "aprilaire", f"{MOCK_MAC}_{unique_id_suffix}"
    )
    assert entry is not None
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all select entities via snapshot."""
    entry = await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_select_air_cleaning_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting an air cleaning event option."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "air_cleaning_event")

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            "option": "allergies",
        },
        blocking=True,
    )

    # event_value=4 (allergies), mode_value=1 (current mode from data)
    mock_client.set_air_cleaning.assert_awaited_once_with(1, 4)


async def test_select_air_cleaning_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting an air cleaning mode option."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "air_cleaning_mode")

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            "option": "automatic",
        },
        blocking=True,
    )

    # mode_value=2 (automatic), event_value=0 (current event from data)
    mock_client.set_air_cleaning.assert_awaited_once_with(2, 0)


async def test_select_fresh_air_event(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting a fresh air event option."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "fresh_air_event")

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            "option": "3hour",
        },
        blocking=True,
    )

    # event_value=2 (3hour), mode_value=1 (current mode from data)
    mock_client.set_fresh_air.assert_awaited_once_with(1, 2)


async def test_select_fresh_air_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting a fresh air mode option."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "fresh_air_mode")

    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id,
            "option": "off",
        },
        blocking=True,
    )

    # mode_value=0 (off), event_value=0 (current event from data)
    mock_client.set_fresh_air.assert_awaited_once_with(0, 0)


async def test_select_not_created_when_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    base_coordinator_data: dict,
) -> None:
    """Test select entities not created when features not available."""
    base_coordinator_data[Attribute.AIR_CLEANING_AVAILABLE] = 0
    base_coordinator_data[Attribute.VENTILATION_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    assert (
        entity_registry.async_get_entity_id(
            SELECT_DOMAIN, "aprilaire", f"{MOCK_MAC}_air_cleaning_event"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            SELECT_DOMAIN, "aprilaire", f"{MOCK_MAC}_fresh_air_event"
        )
        is None
    )

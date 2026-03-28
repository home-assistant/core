"""Tests for the Aprilaire humidifier platform."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.HUMIDIFIER]


pytestmark = [
    pytest.mark.usefixtures("mock_aprilaire"),
]


def _get_entity_id(
    entity_registry: er.EntityRegistry, unique_id_suffix: str
) -> str:
    """Get entity_id from the entity registry by unique_id suffix."""
    entry = entity_registry.async_get_entity_id(
        HUMIDIFIER_DOMAIN, "aprilaire", f"{MOCK_MAC}_{unique_id_suffix}"
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
    """Test all humidifier entities via snapshot."""
    entry = await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_humidifier_set_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting humidifier humidity."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "humidifier")

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: entity_id,
            "humidity": 40,
        },
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_awaited_once_with(40)


async def test_dehumidifier_set_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setting dehumidifier humidity."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "dehumidifier")

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: entity_id,
            "humidity": 50,
        },
        blocking=True,
    )

    mock_client.set_dehumidification_setpoint.assert_awaited_once_with(50)


async def test_humidifier_turn_on(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test turning on the humidifier."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "humidifier")

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_awaited()


async def test_humidifier_turn_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test turning off the humidifier."""
    await setup_integration(hass, mock_config_entry)
    entity_id = _get_entity_id(entity_registry, "humidifier")

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_awaited_once_with(0)


async def test_humidifier_not_created_when_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    base_coordinator_data: dict,
) -> None:
    """Test humidifier entity not created when humidification not available."""
    base_coordinator_data[Attribute.HUMIDIFICATION_AVAILABLE] = 0
    base_coordinator_data[Attribute.DEHUMIDIFICATION_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    assert (
        entity_registry.async_get_entity_id(
            HUMIDIFIER_DOMAIN, "aprilaire", f"{MOCK_MAC}_humidifier"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            HUMIDIFIER_DOMAIN, "aprilaire", f"{MOCK_MAC}_dehumidifier"
        )
        is None
    )

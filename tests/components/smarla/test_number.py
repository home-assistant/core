"""Test number platform for Swing2Sleep Smarla integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pysmarlaapi.federwiege.classes import Property
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_number_property() -> MagicMock:
    """Mock a number property."""
    mock = MagicMock(spec=Property)
    mock.get.return_value = 1
    return mock


@pytest.fixture(autouse=True)
def number_platform_patch() -> Generator:
    """Limit integration to number platform."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.NUMBER]),
    ):
        yield


async def test_entities(
    hass: HomeAssistant,
    mock_federwiege: MagicMock,
    mock_number_property: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    mock_federwiege.get_property.return_value = mock_number_property

    assert await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "parameter"),
    [(SERVICE_SET_VALUE, 100)],
)
async def test_number_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    mock_number_property: MagicMock,
    service: str,
    parameter: int,
) -> None:
    """Test Smarla Number set behavior."""
    mock_federwiege.get_property.return_value = mock_number_property

    assert await setup_integration(hass, mock_config_entry)

    # Turn on
    await hass.services.async_call(
        NUMBER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "number.smarla_intensity", ATTR_VALUE: parameter},
        blocking=True,
    )
    mock_number_property.set.assert_called_once_with(parameter)


async def test_number_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    mock_number_property: MagicMock,
) -> None:
    """Test Smarla Number callback."""
    mock_federwiege.get_property.return_value = mock_number_property

    assert await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.smarla_intensity").state == "1"

    mock_number_property.get.return_value = 100

    await update_property_listeners(mock_number_property)
    await hass.async_block_till_done()

    assert hass.states.get("number.smarla_intensity").state == "100"

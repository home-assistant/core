"""Test switch platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

from pysmarlaapi.federwiege.classes import Property
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_switch_property() -> MagicMock:
    """Mock a switch property."""
    mock = MagicMock(spec=Property)
    mock.get.return_value = False
    return mock


async def test_entities(
    hass: HomeAssistant,
    mock_federwiege: MagicMock,
    mock_switch_property: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    mock_federwiege.get_property.return_value = mock_switch_property

    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service", "parameter"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_switch_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    mock_switch_property: MagicMock,
    service: str,
    parameter: bool,
) -> None:
    """Test Smarla Switch on/off behavior."""
    mock_federwiege.get_property.return_value = mock_switch_property

    assert await setup_integration(hass, mock_config_entry)

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.smarla"},
        blocking=True,
    )
    mock_switch_property.set.assert_called_once_with(parameter)


async def test_switch_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    mock_switch_property: MagicMock,
) -> None:
    """Test Smarla Switch callback."""
    mock_federwiege.get_property.return_value = mock_switch_property

    assert await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.smarla").state == STATE_OFF

    mock_switch_property.get.return_value = True

    await update_property_listeners(mock_switch_property)
    await hass.async_block_till_done()

    assert hass.states.get("switch.smarla").state == STATE_ON

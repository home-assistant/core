"""Tests for selects."""

from unittest.mock import AsyncMock, MagicMock, patch

from ohme import ChargerMode
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Ohme selects."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test selecting an option in the Ohme select entity."""
    mock_client.mode = ChargerMode.SMART_CHARGE
    mock_client.async_set_mode = AsyncMock()

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.ohme_home_pro_charge_mode")
    assert state is not None
    assert state.state == "smart_charge"

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.ohme_home_pro_charge_mode",
            "option": "max_charge",
        },
        blocking=True,
    )

    mock_client.async_set_mode.assert_called_once_with("max_charge")
    assert state.state == "smart_charge"


async def test_select_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that the select entity shows as unavailable when no mode is set."""
    mock_client.mode = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.ohme_home_pro_charge_mode")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

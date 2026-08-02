"""Test sensors."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_config_api: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_account_owner_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test the account owner attribute is exposed."""
    account = mock_config_api.return_value.get_accounts.return_value[0]
    account.account_owner = {"id": "900000010", "displayName": "Alex"}
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.return_value[
        account.id
    ].account_owner = account.account_owner

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert any(
        state.attributes.get("account_owner") == "Alex"
        for state in hass.states.async_all("sensor")
    )

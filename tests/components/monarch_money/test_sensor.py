"""Test sensors."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.monarch_money.const import DOMAIN
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


@pytest.mark.parametrize(
    ("account_owner", "expected_state"),
    [
        pytest.param(
            {"id": "900000010", "displayName": "Alex"},
            "Alex",
            id="display_name",
        ),
        pytest.param(
            {"id": "900000010", "displayName": "", "name": "Alex"},
            "Alex",
            id="name_fallback",
        ),
        pytest.param(
            {"id": "900000010", "displayName": "  ", "name": "  "},
            "unknown",
            id="empty_names",
        ),
        pytest.param(None, "unknown", id="no_owner"),
    ],
)
async def test_account_owner_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    entity_registry: er.EntityRegistry,
    account_owner: dict[str, str] | None,
    expected_state: str,
) -> None:
    """Test the account owner is exposed as a sensor on the account device."""
    account = mock_config_api.return_value.get_accounts.return_value[0]
    account.account_owner = account_owner
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.return_value[
        account.id
    ].account_owner = account_owner

    with patch("homeassistant.components.monarch_money.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    subscription_id = (
        mock_config_api.return_value.get_subscription_details.return_value.id
    )
    owner_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_{account.id}_owner"
    )
    age_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{subscription_id}_{account.id}_age"
    )

    assert owner_entity_id is not None
    assert age_entity_id is not None
    owner_state = hass.states.get(owner_entity_id)
    age_state = hass.states.get(age_entity_id)
    assert owner_state is not None
    assert age_state is not None
    assert owner_state.state == expected_state
    assert "account_owner" not in age_state.attributes
    owner_entry = entity_registry.async_get(owner_entity_id)
    age_entry = entity_registry.async_get(age_entity_id)
    assert owner_entry is not None
    assert age_entry is not None
    assert owner_entry.device_id == age_entry.device_id

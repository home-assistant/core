"""Tests for the permissions module."""

from homeassistant.auth.permissions import filter_entity_ids_by_permission
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.core import HomeAssistant

from tests.common import MockUser


async def test_filter_entity_ids_by_permission_admin(hass: HomeAssistant) -> None:
    """Test admins receive the input entity IDs unchanged."""
    user = MockUser(is_owner=True)
    user.mock_policy({"entities": {"entity_ids": {"light.allowed": True}}})
    assert user.is_admin

    assert filter_entity_ids_by_permission(
        user, ["light.allowed", "light.forbidden"], POLICY_READ
    ) == ["light.allowed", "light.forbidden"]


async def test_filter_entity_ids_by_permission_access_all(hass: HomeAssistant) -> None:
    """Test users with access_all_entities receive the input unchanged."""
    user = MockUser()
    user.mock_policy({"entities": {"all": True}})
    assert not user.is_admin

    assert filter_entity_ids_by_permission(
        user, ["light.a", "light.b"], POLICY_READ
    ) == ["light.a", "light.b"]


async def test_filter_entity_ids_by_permission_filtered(hass: HomeAssistant) -> None:
    """Test users without full access have entity IDs filtered."""
    user = MockUser()
    user.mock_policy({"entities": {"entity_ids": {"light.allowed": True}}})
    assert not user.is_admin

    assert filter_entity_ids_by_permission(
        user, ["light.allowed", "light.forbidden"], POLICY_READ
    ) == ["light.allowed"]


async def test_filter_entity_ids_by_permission_empty(hass: HomeAssistant) -> None:
    """Test users with no permitted entities receive an empty list."""
    user = MockUser()
    user.mock_policy({})
    assert not user.is_admin

    assert filter_entity_ids_by_permission(user, ["light.forbidden"], POLICY_READ) == []

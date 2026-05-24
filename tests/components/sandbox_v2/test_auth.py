"""Phase 7 tests for the sandbox_v2 scoped-auth helpers."""

import pytest

from homeassistant.components.sandbox_v2.auth import (
    SANDBOX_TOKEN_SCOPES,
    async_get_or_create_sandbox_user,
    async_issue_sandbox_access_token,
)
from homeassistant.core import HomeAssistant


async def test_sandbox_token_scopes_allowlist() -> None:
    """The scope set covers `sandbox_v2/*` plus the minimum auth allow-list."""
    assert "sandbox_v2/" in SANDBOX_TOKEN_SCOPES
    assert "auth/current_user" in SANDBOX_TOKEN_SCOPES
    # The set should not pull in broader auth surface like sign_path.
    assert "auth/sign_path" not in SANDBOX_TOKEN_SCOPES
    # No service-call shortcut.
    assert "call_service" not in SANDBOX_TOKEN_SCOPES


async def test_get_or_create_user_is_idempotent(hass: HomeAssistant) -> None:
    """Calling the helper twice for the same group returns the same user."""
    user = await async_get_or_create_sandbox_user(hass, "built-in")
    assert user.system_generated is True
    assert user.is_active is True
    assert user.name == "Sandbox v2: built-in"

    again = await async_get_or_create_sandbox_user(hass, "built-in")
    assert again.id == user.id


@pytest.mark.parametrize("group", ["built-in", "custom", "main"])
async def test_issue_token_returns_valid_access_token(
    hass: HomeAssistant, group: str
) -> None:
    """The issued access token is a JWT that validates back to a scoped refresh token."""
    token = await async_issue_sandbox_access_token(hass, group)
    assert isinstance(token, str)
    assert token  # not empty

    refresh = hass.auth.async_validate_access_token(token)
    assert refresh is not None
    assert refresh.scopes == SANDBOX_TOKEN_SCOPES
    assert refresh.user.system_generated is True
    assert refresh.user.name == f"Sandbox v2: {group}"


async def test_issue_token_reuses_refresh_token(hass: HomeAssistant) -> None:
    """Second call reuses the existing scoped refresh token (no churn)."""
    token_a = await async_issue_sandbox_access_token(hass, "built-in")
    token_b = await async_issue_sandbox_access_token(hass, "built-in")

    refresh_a = hass.auth.async_validate_access_token(token_a)
    refresh_b = hass.auth.async_validate_access_token(token_b)

    assert refresh_a is not None
    assert refresh_b is not None
    assert refresh_a.id == refresh_b.id


async def test_per_group_users_are_distinct(hass: HomeAssistant) -> None:
    """Different groups get different system users and different tokens."""
    builtin = await async_get_or_create_sandbox_user(hass, "built-in")
    custom = await async_get_or_create_sandbox_user(hass, "custom")

    assert builtin.id != custom.id

    builtin_token = await async_issue_sandbox_access_token(hass, "built-in")
    custom_token = await async_issue_sandbox_access_token(hass, "custom")
    assert builtin_token != custom_token

"""Tests for the Aquarite config flow.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
They validate the config flow, reauth, reconfigure, and options flow steps.
Run with: pytest tests/test_config_flow.py (requires HA test environment)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from homeassistant import config_entries  # noqa: E402
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402

from custom_components.aquarite.const import (  # noqa: E402
    CONF_HEALTH_CHECK_INTERVAL,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DOMAIN,
)

PATCH_AUTH = "custom_components.aquarite.config_flow.AquariteAuth"
PATCH_CLIENT = "custom_components.aquarite.config_flow.AquariteClient"
PATCH_SETUP = "custom_components.aquarite.async_setup_entry"


@pytest.fixture
def mock_setup_entry():
    """Prevent actual setup during config flow tests."""
    with patch(PATCH_SETUP, return_value=True) as mock:
        yield mock


def _mock_auth_and_client(pools=None):
    """Return patched auth and client context managers."""
    if pools is None:
        pools = {MOCK_POOL_ID: MOCK_POOL_NAME}
    auth = AsyncMock()
    client = AsyncMock()
    client.get_pools.return_value = pools
    return (
        patch(PATCH_AUTH, return_value=auth),
        patch(PATCH_CLIENT, return_value=client),
        auth,
    )


# ── User + Pool Steps ─────────────────────────────────────────────


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the auth form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_to_pool_step(hass: HomeAssistant) -> None:
    """Test transition from user step to pool selection."""
    patch_auth, patch_client, _ = _mock_auth_and_client()
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pool"


async def test_full_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test the full config flow creates an entry."""
    patch_auth, patch_client, _ = _mock_auth_and_client()
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_POOL_NAME
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        "pool_id": MOCK_POOL_ID,
    }


# ── Error Handling ────────────────────────────────────────────────


async def test_auth_error(hass: HomeAssistant) -> None:
    """Test authentication error is handled."""
    from aioaquarite import AuthenticationError

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error during auth is handled."""
    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = RuntimeError("Connection refused")
        mock_auth_cls.return_value = mock_auth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown_error"}


async def test_no_pools_found(hass: HomeAssistant) -> None:
    """Test no pools found error."""
    patch_auth, patch_client, _ = _mock_auth_and_client(pools={})
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_pools_found"}


async def test_duplicate_pool_aborts(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test that adding a pool that already exists aborts."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    # Create the first entry
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Try to add the same pool again
    patch_auth2, patch_client2, _ = _mock_auth_and_client()
    with patch_auth2, patch_client2:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ── Reauth Flow ───────────────────────────────────────────────────


async def test_reauth_flow_shows_form(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reauth flow shows credential form."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    # Create entry first
    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Start reauth
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reauth flow succeeds with valid credentials."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth

        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new@example.com", CONF_PASSWORD: "newpass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new@example.com"


async def test_reauth_flow_auth_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reauth flow handles auth error."""
    from aioaquarite import AuthenticationError

    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "bad@example.com", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


# ── Reconfigure Flow ──────────────────────────────────────────────


async def test_reconfigure_flow_shows_form(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reconfigure flow shows credential form."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reconfigure flow succeeds with valid credentials."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth_cls.return_value = mock_auth

        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "updated@example.com", CONF_PASSWORD: "updatedpass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_USERNAME] == "updated@example.com"


async def test_reconfigure_flow_auth_error(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test reconfigure flow handles auth error."""
    from aioaquarite import AuthenticationError

    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "bad@example.com", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_error"}


# ── Options Flow ──────────────────────────────────────────────────


async def test_options_flow(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test the options flow allows changing health check interval."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HEALTH_CHECK_INTERVAL: 600},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HEALTH_CHECK_INTERVAL] == 600


async def test_options_flow_default(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """Test options flow uses default health check interval."""
    patch_auth, patch_client, _ = _mock_auth_and_client()

    with patch_auth, patch_client:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"pool_id": MOCK_POOL_ID},
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"]
    schema_dict = schema({})
    assert schema_dict[CONF_HEALTH_CHECK_INTERVAL] == DEFAULT_HEALTH_CHECK_INTERVAL

"""Tests for mijn_ista config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from mijn_ista_api import MijnIstaAuthError, MijnIstaConnectionError
from custom_components.mijn_ista.const import CONF_UPDATE_INTERVAL, DOMAIN

from .conftest import MOCK_USER_VALUES

VALID_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "secret",
    CONF_UPDATE_INTERVAL: 12,
}


def _patch_api(authenticate=None, get_user_values=None):
    """Return a context manager that patches MijnIstaAPI in config_flow and blocks real setup."""
    from contextlib import ExitStack, contextmanager

    mock_instance = AsyncMock()
    mock_instance.authenticate = authenticate or AsyncMock()
    mock_instance.get_user_values = get_user_values or AsyncMock(
        return_value=MOCK_USER_VALUES
    )

    @contextmanager
    def _ctx():
        with (
            patch(
                "custom_components.mijn_ista.config_flow.MijnIstaAPI",
                return_value=mock_instance,
            ),
            patch(
                "custom_components.mijn_ista.async_setup_entry",
                return_value=True,
            ),
        ):
            yield mock_instance

    return _ctx()


# ---------------------------------------------------------------------------
# User step
# ---------------------------------------------------------------------------


class TestUserStep:
    async def test_shows_form_on_get(self, hass: HomeAssistant):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_success_creates_entry(self, hass: HomeAssistant):
        with _patch_api():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "ista NL — Test User"
        data = result["data"]
        assert data[CONF_USERNAME] == "test@example.com"
        assert data[CONF_PASSWORD] == "secret"
        assert "language" not in data  # language field removed in v2
        options = result["options"]
        assert options[CONF_UPDATE_INTERVAL] == 12

    async def test_invalid_auth_shows_error(self, hass: HomeAssistant):
        auth_mock = AsyncMock(side_effect=MijnIstaAuthError)
        with _patch_api(authenticate=auth_mock):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_cannot_connect_shows_error(self, hass: HomeAssistant):
        auth_mock = AsyncMock(side_effect=MijnIstaConnectionError)
        with _patch_api(authenticate=auth_mock):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_unexpected_exception_shows_unknown_error(self, hass: HomeAssistant):
        auth_mock = AsyncMock(side_effect=RuntimeError("boom"))
        with _patch_api(authenticate=auth_mock):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_duplicate_entry_aborts(self, hass: HomeAssistant):
        # Create the first entry
        with _patch_api():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        # Try a second entry with the same username
        with _patch_api():
            result2 = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result2 = await hass.config_entries.flow.async_configure(
                result2["flow_id"], user_input=VALID_INPUT
            )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"

    async def test_display_name_falls_back_to_username(self, hass: HomeAssistant):
        user_values_no_name = {**MOCK_USER_VALUES, "DisplayName": None}
        user_mock = AsyncMock(return_value=user_values_no_name)
        with _patch_api(get_user_values=user_mock):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert "test@example.com" in result["title"]


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    async def _create_entry(self, hass: HomeAssistant) -> config_entries.ConfigEntry:
        with _patch_api():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )
            await hass.async_block_till_done()
        return hass.config_entries.async_entries(DOMAIN)[0]

    async def test_options_flow_shows_form(self, hass: HomeAssistant):
        entry = await self._create_entry(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_updates_interval(self, hass: HomeAssistant):
        entry = await self._create_entry(hass)
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_UPDATE_INTERVAL: 6}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_UPDATE_INTERVAL] == 6


# ---------------------------------------------------------------------------
# Reconfigure step
# ---------------------------------------------------------------------------


class TestReconfigureStep:
    async def _create_entry(self, hass: HomeAssistant) -> config_entries.ConfigEntry:
        with _patch_api():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )
            await hass.async_block_till_done()
        return hass.config_entries.async_entries(DOMAIN)[0]

    async def test_reconfigure_shows_form(self, hass: HomeAssistant):
        entry = await self._create_entry(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    async def test_reconfigure_success_updates_credentials(self, hass: HomeAssistant):
        entry = await self._create_entry(hass)
        with _patch_api():
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: "new@example.com", CONF_PASSWORD: "newpass"},
            )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.data[CONF_USERNAME] == "new@example.com"
        assert entry.data[CONF_PASSWORD] == "newpass"

    async def test_reconfigure_bad_credentials_shows_error(self, hass: HomeAssistant):
        entry = await self._create_entry(hass)
        auth_mock = AsyncMock(side_effect=MijnIstaAuthError)
        with _patch_api(authenticate=auth_mock):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: "bad@example.com", CONF_PASSWORD: "wrong"},
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

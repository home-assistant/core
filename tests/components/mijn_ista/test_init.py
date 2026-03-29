"""Tests for mijn_ista __init__ (setup, unload, migration)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.mijn_ista.const import CONF_UPDATE_INTERVAL, DOMAIN

from .conftest import MOCK_AVG_VALUES, MOCK_MONTH_VALUES, MOCK_USER_VALUES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENTRY_DATA = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "secret"}
ENTRY_OPTIONS = {CONF_UPDATE_INTERVAL: 24}


def _make_mock_coordinator(hass):
    """Return a coordinator stub that doesn't make real HTTP calls."""
    coord = MagicMock()
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.async_unload = AsyncMock(return_value=True)
    coord.data = {"test-cuid": MagicMock()}
    coord.hass = hass
    return coord


# ---------------------------------------------------------------------------
# async_setup_entry
# ---------------------------------------------------------------------------


class TestSetupEntry:
    async def test_setup_entry_stores_coordinator_in_runtime_data(
        self, hass: HomeAssistant
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options=ENTRY_OPTIONS)
        entry.add_to_hass(hass)

        with (
            patch("custom_components.mijn_ista.MijnIstaAPI"),
            patch(
                "custom_components.mijn_ista.MijnIstaCoordinator",
                return_value=_make_mock_coordinator(hass),
            ),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=True,
            ),
        ):
            result = await hass.config_entries.async_setup(entry.entry_id)

        assert result is True
        assert entry.runtime_data is not None

    async def test_setup_entry_uses_nl_lang_for_dutch_hass(self, hass: HomeAssistant):
        """When HA language is Dutch, API should be initialised with nl-NL."""
        hass.config.language = "nl"
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options=ENTRY_OPTIONS)
        entry.add_to_hass(hass)

        captured_lang = {}

        def _capture_api(session, username, password, lang="en-GB"):
            captured_lang["lang"] = lang
            m = MagicMock()
            return m

        with (
            patch(
                "custom_components.mijn_ista.MijnIstaAPI", side_effect=_capture_api
            ),
            patch(
                "custom_components.mijn_ista.MijnIstaCoordinator",
                return_value=_make_mock_coordinator(hass),
            ),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=True,
            ),
        ):
            await hass.config_entries.async_setup(entry.entry_id)

        assert captured_lang.get("lang") == "nl-NL"

    async def test_setup_entry_uses_en_gb_for_english_hass(self, hass: HomeAssistant):
        hass.config.language = "en"
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options=ENTRY_OPTIONS)
        entry.add_to_hass(hass)

        captured_lang = {}

        def _capture_api(session, username, password, lang="en-GB"):
            captured_lang["lang"] = lang
            return MagicMock()

        with (
            patch(
                "custom_components.mijn_ista.MijnIstaAPI", side_effect=_capture_api
            ),
            patch(
                "custom_components.mijn_ista.MijnIstaCoordinator",
                return_value=_make_mock_coordinator(hass),
            ),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=True,
            ),
        ):
            await hass.config_entries.async_setup(entry.entry_id)

        assert captured_lang.get("lang") == "en-GB"


# ---------------------------------------------------------------------------
# async_unload_entry
# ---------------------------------------------------------------------------


class TestUnloadEntry:
    async def test_unload_entry_succeeds(self, hass: HomeAssistant):
        entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options=ENTRY_OPTIONS)
        entry.add_to_hass(hass)

        coord = _make_mock_coordinator(hass)

        with (
            patch("custom_components.mijn_ista.MijnIstaAPI"),
            patch(
                "custom_components.mijn_ista.MijnIstaCoordinator",
                return_value=coord,
            ),
            patch(
                "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
                return_value=True,
            ),
        ):
            await hass.config_entries.async_setup(entry.entry_id)

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ):
            result = await hass.config_entries.async_unload(entry.entry_id)

        assert result is True


# ---------------------------------------------------------------------------
# async_migrate_entry
# ---------------------------------------------------------------------------


class TestMigrateEntry:
    async def test_migrate_v1_removes_language_field(self, hass: HomeAssistant):
        """Version 1 entries have a 'language' key that must be removed in v2."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={**ENTRY_DATA, "language": "en"},
            options=ENTRY_OPTIONS,
            version=1,
        )
        entry.add_to_hass(hass)

        from custom_components.mijn_ista import async_migrate_entry

        result = await async_migrate_entry(hass, entry)

        assert result is True
        assert "language" not in entry.data
        assert entry.version == 2

    async def test_migrate_v2_is_noop(self, hass: HomeAssistant):
        """Already-v2 entries should pass through unchanged."""
        entry = MockConfigEntry(
            domain=DOMAIN, data=ENTRY_DATA, options=ENTRY_OPTIONS, version=2
        )
        entry.add_to_hass(hass)

        from custom_components.mijn_ista import async_migrate_entry

        result = await async_migrate_entry(hass, entry)
        assert result is True
        assert entry.version == 2


# ---------------------------------------------------------------------------
# Import helper (avoids importing pytest_homeassistant_custom_component everywhere)
# ---------------------------------------------------------------------------


from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

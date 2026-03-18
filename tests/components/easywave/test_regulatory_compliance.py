"""Tests for regulatory compliance in the Easywave Core integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.easywave import async_setup_entry
from homeassistant.components.easywave.const import (
    DOMAIN,
    FREQUENCY_868MHZ,
    FREQUENCY_ALLOWED_COUNTRIES,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


def _patch_for_successful_setup() -> tuple:
    """Return context managers for a successful setup."""
    mock_coordinator = AsyncMock()
    mock_coordinator.async_setup = AsyncMock(return_value=True)
    mock_coordinator.async_shutdown = AsyncMock()
    return (
        patch("homeassistant.components.easywave.RX11Transceiver"),
        patch(
            "homeassistant.components.easywave.EasywaveCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ),
    )


class TestCountryValidation:
    """Test country validation for radio frequencies."""

    def test_all_allowed_countries_in_frequency_list(self) -> None:
        """Test that all expected 868MHz countries are in the list."""
        allowed = FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]

        essential_eu = {"DE", "FR", "IT", "ES", "NL", "BE", "AT", "CZ", "PL"}
        assert essential_eu.issubset(allowed)

        nordic = {"SE", "NO", "DK", "FI"}
        assert nordic.issubset(allowed)

        assert "GB" in allowed

        cept_non_eu = {"CH", "IS", "LI"}
        assert cept_non_eu.issubset(allowed)

    def test_country_code_case_insensitive(self) -> None:
        """Test that country code comparison is case-insensitive."""
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "de") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "DE") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "De") is True

    def test_disallowed_countries(self) -> None:
        """Test that non-CEPT countries are blocked."""
        for country in ("US", "JP", "CN", "BR", "AU", "RU", "IN"):
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is False

    def test_none_country_allowed(self) -> None:
        """Test that None country (not configured) is allowed."""
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, None) is True

    def test_unknown_frequency_allowed(self) -> None:
        """Test that unknown frequency is allowed (conservative)."""
        assert is_country_allowed_for_frequency("unknown", "US") is True


class TestFrequencyDetection:
    """Test frequency detection from USB device PID."""

    def test_rx11_pid_returns_868mhz(self) -> None:
        """Test that RX11 PID returns 868 MHz."""
        assert get_frequency_for_pid(0x1014) == FREQUENCY_868MHZ

    def test_unknown_pid_returns_none(self) -> None:
        """Test that unknown PID returns None."""
        assert get_frequency_for_pid(0x9999) is None

    def test_none_pid_returns_none(self) -> None:
        """Test that None PID returns None."""
        assert get_frequency_for_pid(None) is None


class TestIntegrationSetupCompliance:
    """Test regulatory compliance enforcement during setup."""

    async def test_setup_succeeds_with_allowed_country(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that setup succeeds when country is allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "DE"

        t_patch, c_patch, f_patch = _patch_for_successful_setup()
        with t_patch, c_patch, f_patch:
            result = await async_setup_entry(hass, mock_config_entry)

        assert result is True

    async def test_setup_fails_with_disallowed_country(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that setup fails when country is not allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "US"

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is False

    async def test_setup_succeeds_with_no_country_configured(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that setup succeeds when no country is configured."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = None

        t_patch, c_patch, f_patch = _patch_for_successful_setup()
        with t_patch, c_patch, f_patch:
            result = await async_setup_entry(hass, mock_config_entry)

        assert result is True

    async def test_repair_issue_created_on_disallowed_country(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that a repair issue is created when country is not allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "US"

        await async_setup_entry(hass, mock_config_entry)

        issues = ir.async_get(hass)
        issue = issues.async_get_issue(
            DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
        )
        assert issue is not None
        assert issue.translation_key == "frequency_not_permitted"
        assert "868 MHz" in str(issue.translation_placeholders)

    async def test_stale_repair_issue_deleted_on_allowed_country(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that stale repair issues are removed when country is allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "FR"

        t_patch, c_patch, f_patch = _patch_for_successful_setup()
        with t_patch, c_patch, f_patch:
            result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        issues = ir.async_get(hass)
        issue = issues.async_get_issue(
            DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
        )
        assert issue is None

    async def test_all_eu_countries_allowed(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test that all EU member states are in the allowed list."""
        eu_countries = {
            "AT",
            "BE",
            "BG",
            "HR",
            "CY",
            "CZ",
            "DK",
            "EE",
            "FI",
            "FR",
            "DE",
            "GR",
            "HU",
            "IE",
            "IT",
            "LV",
            "LT",
            "LU",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SK",
            "SI",
            "ES",
            "SE",
        }
        for country in eu_countries:
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is True

    async def test_uk_and_post_brexit_aliases(self) -> None:
        """Test that both GB and UK aliases work."""
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "GB") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "UK") is True

    async def test_cept_non_eu_members_allowed(self) -> None:
        """Test that non-EU CEPT members are allowed."""
        for country in ("CH", "NO", "IS", "LI"):
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is True

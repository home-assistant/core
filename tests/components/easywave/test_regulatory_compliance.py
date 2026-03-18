"""Tests for regulatory compliance in the Easywave Core integration."""
from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from homeassistant.core import HomeAssistant

from homeassistant.components.easywave import async_setup_entry
from homeassistant.components.easywave.const import (
    CONF_USB_PID,
    DOMAIN,
    FREQUENCY_868MHZ,
    FREQUENCY_ALLOWED_COUNTRIES,
    is_country_allowed_for_frequency,
    get_frequency_for_pid,
)


class TestCountryValidation:
    """Test country validation for radio frequencies."""

    def test_all_allowed_countries_in_frequency_list(self):
        """Test that all expected 868MHz countries are in the list."""
        allowed = FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]
        
        # Essential EU countries
        essential_eu = {"DE", "FR", "IT", "ES", "NL", "BE", "AT", "CZ", "PL"}
        assert essential_eu.issubset(allowed)
        
        # Nordic countries
        nordic = {"SE", "NO", "DK", "FI"}
        assert nordic.issubset(allowed)
        
        # Post-Brexit UK
        assert "GB" in allowed
        
        # CEPT non-EU
        cept_non_eu = {"CH", "IS", "LI"}
        assert cept_non_eu.issubset(allowed)

    def test_country_code_case_insensitive(self):
        """Test that country code comparison is case-insensitive."""
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "de") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "DE") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "De") is True

    def test_disallowed_countries(self):
        """Test that non-CEPT countries are blocked."""
        disallowed = ["US", "JP", "CN", "BR", "AU", "RU", "IN"]
        for country in disallowed:
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is False

    def test_none_country_allowed(self):
        """Test that None country (not configured) is allowed."""
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, None) is True

    def test_unknown_frequency_allowed(self):
        """Test that unknown frequency is allowed (conservative)."""
        assert is_country_allowed_for_frequency("unknown", "US") is True


class TestFrequencyDetection:
    """Test frequency detection from USB device PID."""

    def test_rx11_pid_returns_868mhz(self):
        """Test that RX11 PID returns 868 MHz."""
        assert get_frequency_for_pid(0x1014) == FREQUENCY_868MHZ

    def test_unknown_pid_returns_none(self):
        """Test that unknown PID returns None."""
        assert get_frequency_for_pid(0x9999) is None

    def test_none_pid_returns_none(self):
        """Test that None PID returns None."""
        assert get_frequency_for_pid(None) is None


class TestIntegrationSetupCompliance:
    """Test regulatory compliance enforcement during setup."""

    @pytest.mark.asyncio
    async def test_setup_succeeds_with_allowed_country(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that setup succeeds when country is allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "DE"  # Germany is allowed
        
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_setup_fails_with_disallowed_country(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that setup fails when country is not allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "US"  # USA is not allowed
        
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_setup_succeeds_with_no_country_configured(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that setup succeeds when no country is configured."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = None
        
        result = await async_setup_entry(hass, mock_config_entry)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_repair_issue_created_on_disallowed_country(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that a repair issue is created when country is not allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "US"
        
        with patch("homeassistant.components.easywave.ir.async_create_issue") as mock_issue:
            with patch("homeassistant.components.easywave.ir.async_delete_issue"):
                await async_setup_entry(hass, mock_config_entry)
        
        # Verify issue was created with correct parameters
        assert mock_issue.called
        call_args = mock_issue.call_args
        assert call_args[0][0] == hass
        assert call_args[0][1] == DOMAIN
        assert "frequency_not_permitted" in call_args[0][2]
        assert call_args[1]["severity"] is not None
        assert call_args[1]["translation_key"] == "frequency_not_permitted"
        assert "868 MHz" in str(call_args[1]["translation_placeholders"])

    @pytest.mark.asyncio
    async def test_stale_repair_issue_deleted_on_allowed_country(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test that stale repair issues are removed when country is allowed."""
        mock_config_entry.add_to_hass(hass)
        hass.config.country = "FR"  # France is allowed
        
        with patch("homeassistant.components.easywave.ir.async_delete_issue") as mock_delete:
            with patch("homeassistant.components.easywave.ir.async_create_issue"):
                await async_setup_entry(hass, mock_config_entry)
        
        # Verify issue deletion was called
        assert mock_delete.called

    @pytest.mark.asyncio
    async def test_all_eu_countries_allowed(self, hass: HomeAssistant, mock_config_entry):
        """Test that all EU member states are in the allowed list."""
        eu_countries = {
            "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE",
            "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT",
            "RO", "SK", "SI", "ES", "SE"
        }
        
        for country in eu_countries:
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is True

    @pytest.mark.asyncio
    async def test_uk_and_post_brexit_aliases(self):
        """Test that both GB and UK aliases work."""
        # Both should be allowed
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "GB") is True
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "UK") is True

    @pytest.mark.asyncio
    async def test_cept_non_eu_members_allowed(self):
        """Test that non-EU CEPT members are allowed."""
        cept_non_eu = {
            "CH",  # Switzerland
            "NO",  # Norway
            "IS",  # Iceland
            "LI",  # Liechtenstein
        }
        
        for country in cept_non_eu:
            assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is True

"""Tests for regulatory compliance in the Easywave Core integration."""

from homeassistant.components.easywave.const import (
    ALLOWED_COUNTRIES_868MHZ,
    DOMAIN,
    FREQUENCY_868MHZ,
    FREQUENCY_ALLOWED_COUNTRIES,
    get_frequency_for_pid,
    is_country_allowed_for_frequency,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import async_setup_easywave_entry, mock_easywave_transceiver

from tests.common import MockConfigEntry

# CEPT member states (ISO 3166-1 alpha-2), per https://www.cept.org/cept/membership-and-observers
CEPT_COUNTRIES_868MHZ: frozenset[str] = frozenset(
    {
        "AD",
        "AL",
        "AT",
        "AZ",
        "BA",
        "BE",
        "BG",
        "CH",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
        "GE",
        "GR",
        "HR",
        "HU",
        "IE",
        "IS",
        "IT",
        "LI",
        "LT",
        "LU",
        "LV",
        "MC",
        "MD",
        "ME",
        "MK",
        "MT",
        "NL",
        "NO",
        "PL",
        "PT",
        "RO",
        "RS",
        "SE",
        "SI",
        "SK",
        "SM",
        "TR",
        "UA",
        "VA",
    }
)


def test_all_allowed_countries_in_frequency_list() -> None:
    """Test that all expected 868MHz countries are in the list."""
    allowed = ALLOWED_COUNTRIES_868MHZ

    assert allowed is FREQUENCY_ALLOWED_COUNTRIES[FREQUENCY_868MHZ]

    essential_eu = {"DE", "FR", "IT", "ES", "NL", "BE", "AT", "CZ", "PL"}
    assert essential_eu.issubset(allowed)

    nordic = {"SE", "NO", "DK", "FI"}
    assert nordic.issubset(allowed)

    assert "GB" in allowed

    assert CEPT_COUNTRIES_868MHZ.issubset(allowed)


def test_country_code_case_insensitive() -> None:
    """Test that country code comparison is case-insensitive."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "de") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "DE") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "De") is True


def test_disallowed_countries() -> None:
    """Test that non-CEPT countries are blocked."""
    for country in ("US", "JP", "CN", "BR", "AU", "RU", "IN"):
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is False


def test_none_country_disallowed() -> None:
    """Test that None country (not configured) blocks the radio."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, None) is False


def test_unknown_frequency_allowed() -> None:
    """Test that unknown frequency is allowed (conservative)."""
    assert is_country_allowed_for_frequency("unknown", "US") is True


def test_rx11_pid_returns_868mhz() -> None:
    """Test that RX11 PID returns 868 MHz."""
    assert get_frequency_for_pid(0x1014) == FREQUENCY_868MHZ


def test_unknown_pid_returns_none() -> None:
    """Test that unknown PID returns None."""
    assert get_frequency_for_pid(0x9999) is None


def test_none_pid_returns_none() -> None:
    """Test that None PID returns None."""
    assert get_frequency_for_pid(None) is None


async def test_setup_succeeds_with_allowed_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that setup succeeds when country is allowed."""
    await async_setup_easywave_entry(hass, mock_config_entry, country="DE")


async def test_setup_fails_with_disallowed_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that setup fails when country is not allowed."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False


async def test_setup_fails_with_no_country_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that setup fails when no country is configured."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False
    assert mock_config_entry.error_reason_translation_key == "country_not_configured"

    # pylint: disable-next=home-assistant-tests-registry-fixtures
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"country_not_configured_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "country_not_configured"


async def test_regulatory_issue_replaces_previous_key(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Changing between unset and disallowed country replaces the repair issue."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = None
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False

    # pylint: disable-next=home-assistant-tests-registry-fixtures
    issues = ir.async_get(hass)
    assert (
        issues.async_get_issue(
            DOMAIN, f"country_not_configured_{mock_config_entry.entry_id}"
        )
        is not None
    )

    hass.config.country = "US"
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id) is False
    await hass.async_block_till_done()

    assert (
        issues.async_get_issue(
            DOMAIN, f"country_not_configured_{mock_config_entry.entry_id}"
        )
        is None
    )
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "frequency_not_permitted"


async def test_country_change_reloads_and_disables_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Changing HA country to a disallowed region reloads and disables Easywave."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config.async_update(country="US")
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "frequency_not_permitted"
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    issues = ir.async_get(hass)
    assert (
        issues.async_get_issue(
            DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
        )
        is not None
    )


async def test_repair_issue_created_on_disallowed_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a repair issue is created when country is not allowed."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # pylint: disable-next=home-assistant-tests-registry-fixtures
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "frequency_not_permitted"
    assert "868 MHz" in str(issue.translation_placeholders)


async def test_stale_repair_issue_deleted_on_allowed_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that stale repair issues are removed when country is allowed."""
    await async_setup_easywave_entry(hass, mock_config_entry, country="FR")

    # pylint: disable-next=home-assistant-tests-registry-fixtures
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is None


async def test_all_eu_countries_allowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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


async def test_uk_and_post_brexit_aliases() -> None:
    """Test that both GB and UK aliases work."""
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "GB") is True
    assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, "UK") is True


async def test_cept_non_eu_members_allowed() -> None:
    """Test that non-EU CEPT members are allowed."""
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
    cept_non_eu = CEPT_COUNTRIES_868MHZ - eu_countries
    for country in sorted(cept_non_eu):
        assert is_country_allowed_for_frequency(FREQUENCY_868MHZ, country) is True

"""Tests for the ecobee integration setup and refresh paths."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyecobee import (
    ECOBEE_API_KEY,
    ECOBEE_PASSWORD,
    ECOBEE_REFRESH_TOKEN,
    ECOBEE_USERNAME,
    EcobeeAuthFailedError,
    EcobeeAuthMfaRequiredError,
    EcobeeAuthUnknownError,
    ExpiredTokenError,
)
import pytest

from homeassistant.components.ecobee.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from . import GENERIC_THERMOSTAT_INFO

from tests.common import MockConfigEntry, async_fire_time_changed


def _api_key_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a registered MockConfigEntry using the PIN/API-key data shape."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key", CONF_REFRESH_TOKEN: "test-refresh-token"},
    )
    entry.add_to_hass(hass)
    return entry


def _credentials_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a registered MockConfigEntry using the username/password data shape."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "test-password",
            CONF_REFRESH_TOKEN: "test-refresh-token",
        },
    )
    entry.add_to_hass(hass)
    return entry


_DEFAULT_THERMOSTATS = object()


def _build_mock_ecobee(
    *,
    refresh_returns: bool = True,
    config: dict | None = None,
    thermostats: list | None = _DEFAULT_THERMOSTATS,
) -> MagicMock:
    """Return a MagicMock shaped like a successfully-refreshed pyecobee.Ecobee."""
    ecobee = MagicMock()
    ecobee.refresh_tokens.return_value = refresh_returns
    ecobee.thermostats = (
        [GENERIC_THERMOSTAT_INFO]
        if thermostats is _DEFAULT_THERMOSTATS
        else thermostats
    )
    ecobee.get_thermostat = lambda index: ecobee.thermostats[index]
    ecobee.config = (
        {ECOBEE_API_KEY: "test-api-key", ECOBEE_REFRESH_TOKEN: "new-refresh-token"}
        if config is None
        else config
    )
    return ecobee


async def _setup_with_mock(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    ecobee: MagicMock,
    *,
    platforms: list[Platform] | None = None,
) -> bool:
    """Set up the entry with a patched pyecobee.Ecobee returning ``ecobee``."""
    with (
        patch("homeassistant.components.ecobee.Ecobee", return_value=ecobee),
        patch(
            "homeassistant.components.ecobee.PLATFORMS",
            [] if platforms is None else platforms,
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return result


def _has_reauth_flow(hass: HomeAssistant) -> bool:
    """Return True if the ecobee config flow has an in-progress reauth flow."""
    return any(
        flow["context"].get("source") == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_setup_succeeds_with_api_key_entry(hass: HomeAssistant) -> None:
    """A PIN/API-key entry sets up cleanly when pyecobee returns thermostats."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee()

    assert await _setup_with_mock(hass, entry, ecobee) is True
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_succeeds_with_credentials_entry(hass: HomeAssistant) -> None:
    """A username/password entry sets up cleanly when pyecobee returns thermostats."""
    entry = _credentials_entry(hass)
    ecobee = _build_mock_ecobee(
        config={
            ECOBEE_USERNAME: "user@example.com",
            ECOBEE_PASSWORD: "test-password",
            ECOBEE_REFRESH_TOKEN: "new-refresh-token",
        }
    )

    assert await _setup_with_mock(hass, entry, ecobee) is True
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_rejects_entry_with_no_credentials(hass: HomeAssistant) -> None:
    """An entry missing both API key and username/password fails setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_REFRESH_TOKEN: "test-refresh-token"}
    )
    entry.add_to_hass(hass)

    assert await _setup_with_mock(hass, entry, _build_mock_ecobee()) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_fails_when_refresh_returns_false(hass: HomeAssistant) -> None:
    """A False return from pyecobee.refresh_tokens aborts setup."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee(refresh_returns=False)

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert not _has_reauth_flow(hass)


async def test_setup_fails_when_no_thermostats(hass: HomeAssistant) -> None:
    """Setup aborts when ecobee.com returns no thermostats."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee(thermostats=None)

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_triggers_reauth_on_mfa_required(hass: HomeAssistant) -> None:
    """EcobeeAuthMfaRequiredError during setup raises ConfigEntryAuthFailed → reauth."""
    entry = _credentials_entry(hass)
    ecobee = _build_mock_ecobee()
    ecobee.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError("mfa")

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert _has_reauth_flow(hass)


async def test_setup_triggers_reauth_on_auth_failed_with_username(
    hass: HomeAssistant,
) -> None:
    """EcobeeAuthFailedError on a credentials entry raises ConfigEntryAuthFailed → reauth."""
    entry = _credentials_entry(hass)
    ecobee = _build_mock_ecobee(
        config={ECOBEE_USERNAME: "user@example.com", ECOBEE_PASSWORD: "test-password"}
    )
    ecobee.refresh_tokens.side_effect = EcobeeAuthFailedError("bad creds")

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert _has_reauth_flow(hass)


async def test_setup_no_reauth_on_auth_failed_without_username(
    hass: HomeAssistant,
) -> None:
    """API-key entries surface EcobeeAuthFailedError as a False return, not reauth."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee(config={ECOBEE_API_KEY: "test-api-key"})
    ecobee.refresh_tokens.side_effect = EcobeeAuthFailedError("bad creds")

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert not _has_reauth_flow(hass)


async def test_setup_no_reauth_on_unknown_error(hass: HomeAssistant) -> None:
    """EcobeeAuthUnknownError is treated as transient — no reauth flow is started."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee()
    ecobee.refresh_tokens.side_effect = EcobeeAuthUnknownError("network")

    assert await _setup_with_mock(hass, entry, ecobee) is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert not _has_reauth_flow(hass)


async def test_setup_recovers_from_expired_token_during_update(
    hass: HomeAssistant,
) -> None:
    """update() catches ExpiredTokenError and triggers refresh() in the same setup pass."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee()
    ecobee.update.side_effect = ExpiredTokenError("expired")

    assert await _setup_with_mock(hass, entry, ecobee) is True
    assert entry.state is ConfigEntryState.LOADED
    # refresh_tokens runs twice: once during async_setup_entry's refresh(), and
    # again from update()'s ExpiredTokenError branch.
    assert ecobee.refresh_tokens.call_count == 2


@pytest.mark.parametrize(
    ("config", "expected_data"),
    [
        (
            {
                ECOBEE_API_KEY: "test-api-key",
                ECOBEE_REFRESH_TOKEN: "fresh-refresh-token",
            },
            {
                CONF_API_KEY: "test-api-key",
                CONF_REFRESH_TOKEN: "fresh-refresh-token",
            },
        ),
        (
            {
                ECOBEE_USERNAME: "user@example.com",
                ECOBEE_PASSWORD: "test-password",
                ECOBEE_REFRESH_TOKEN: "fresh-refresh-token",
            },
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "test-password",
                CONF_REFRESH_TOKEN: "fresh-refresh-token",
            },
        ),
    ],
    ids=["api_key", "credentials"],
)
async def test_setup_persists_refreshed_credentials_to_entry(
    hass: HomeAssistant,
    config: dict,
    expected_data: dict,
) -> None:
    """A successful refresh writes the new refresh_token back to the entry."""
    entry = (
        _credentials_entry(hass) if ECOBEE_USERNAME in config else _api_key_entry(hass)
    )
    ecobee = _build_mock_ecobee(config=config)

    assert await _setup_with_mock(hass, entry, ecobee) is True
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == expected_data


async def test_runtime_refresh_persists_new_refresh_token(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A natural runtime refresh writes the rotated refresh_token back to the entry.

    Sets up successfully, then advances time past the climate platform's scan
    interval + EcobeeData's MIN_TIME_BETWEEN_UPDATES throttle so a real entity
    poll calls update() → ExpiredTokenError → refresh() → entry update.
    """
    entry = _credentials_entry(hass)
    ecobee = _build_mock_ecobee(
        config={
            ECOBEE_USERNAME: "user@example.com",
            ECOBEE_PASSWORD: "test-password",
            ECOBEE_REFRESH_TOKEN: "first-refresh-token",
        }
    )

    assert (
        await _setup_with_mock(hass, entry, ecobee, platforms=[Platform.CLIMATE])
        is True
    )
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_REFRESH_TOKEN] == "first-refresh-token"

    ecobee.update.side_effect = ExpiredTokenError("expired")
    ecobee.config = {
        ECOBEE_USERNAME: "user@example.com",
        ECOBEE_PASSWORD: "test-password",
        ECOBEE_REFRESH_TOKEN: "rotated-refresh-token",
    }

    freezer.tick(timedelta(seconds=300))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.data[CONF_REFRESH_TOKEN] == "rotated-refresh-token"

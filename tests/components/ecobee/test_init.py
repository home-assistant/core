"""Tests for the ecobee integration setup, refresh, and update paths."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

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

from homeassistant.components.ecobee import EcobeeData
from homeassistant.components.ecobee.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def disable_real_requests() -> Generator[None]:
    """Block any accidental real HTTP calls from the integration code."""
    with patch("homeassistant.components.ecobee.Ecobee", autospec=False):
        yield


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


def _build_mock_ecobee(*, refresh_returns: bool = True) -> MagicMock:
    """Return a MagicMock that looks like a successfully-refreshed Ecobee instance."""
    ecobee = MagicMock()
    ecobee.refresh_tokens.return_value = refresh_returns
    ecobee.thermostats = [{"identifier": 1, "name": "Thermostat"}]
    ecobee.config = {
        ECOBEE_API_KEY: "test-api-key",
        ECOBEE_REFRESH_TOKEN: "new-refresh-token",
    }
    return ecobee


async def test_setup_entry_returns_false_when_refresh_fails(
    hass: HomeAssistant,
) -> None:
    """A False return from EcobeeData.refresh aborts setup."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee(refresh_returns=False)

    with patch("homeassistant.components.ecobee.Ecobee", return_value=ecobee):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_returns_false_when_no_thermostats(
    hass: HomeAssistant,
) -> None:
    """Setup aborts when ecobee.com returns no thermostats."""
    entry = _api_key_entry(hass)
    ecobee = _build_mock_ecobee()
    ecobee.thermostats = None

    with patch("homeassistant.components.ecobee.Ecobee", return_value=ecobee):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_ecobee_data_credentials_branch(hass: HomeAssistant) -> None:
    """EcobeeData uses the username/password branch when no api_key is present."""
    entry = _credentials_entry(hass)

    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        EcobeeData(
            hass,
            entry,
            api_key=None,
            username="user@example.com",
            password="hunter2",
            refresh_token="rt",
        )
        mock_ecobee_cls.assert_called_once_with(
            config={
                ECOBEE_USERNAME: "user@example.com",
                ECOBEE_PASSWORD: "hunter2",
                ECOBEE_REFRESH_TOKEN: "rt",
            }
        )


async def test_ecobee_data_rejects_missing_credentials(hass: HomeAssistant) -> None:
    """EcobeeData raises when nothing is supplied."""
    entry = _api_key_entry(hass)
    with pytest.raises(ValueError, match="No ecobee credentials"):
        EcobeeData(hass, entry)


async def test_update_refreshes_on_expired_token(hass: HomeAssistant) -> None:
    """update() catches ExpiredTokenError and triggers a refresh."""
    entry = _api_key_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.return_value = True
        ecobee.config = {
            ECOBEE_API_KEY: "test-api-key",
            ECOBEE_REFRESH_TOKEN: "new-rt",
        }
        # update() raises ExpiredTokenError; the except branch calls refresh(),
        # which invokes refresh_tokens() (mocked to succeed).
        ecobee.update.side_effect = ExpiredTokenError("expired")

        runtime = EcobeeData(
            hass, entry, api_key="test-api-key", refresh_token="old-rt"
        )
        await runtime.update()

    # update() was called once and refresh_tokens() ran in response to the expiry.
    ecobee.refresh_tokens.assert_called_once_with()


async def test_refresh_raises_config_entry_auth_failed_on_mfa(
    hass: HomeAssistant,
) -> None:
    """Refresh translates EcobeeAuthMfaRequiredError into ConfigEntryAuthFailed."""
    entry = _credentials_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.side_effect = EcobeeAuthMfaRequiredError("mfa")

        runtime = EcobeeData(
            hass,
            entry,
            username="user@example.com",
            password="pw",
            refresh_token="rt",
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await runtime.refresh()


async def test_refresh_raises_config_entry_auth_failed_on_failed_with_username(
    hass: HomeAssistant,
) -> None:
    """Refresh raises ConfigEntryAuthFailed when creds rejected and username stored."""
    entry = _credentials_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.side_effect = EcobeeAuthFailedError("bad pw")
        ecobee.config = {
            ECOBEE_USERNAME: "user@example.com",
            ECOBEE_PASSWORD: "pw",
        }

        runtime = EcobeeData(
            hass,
            entry,
            username="user@example.com",
            password="pw",
            refresh_token="rt",
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await runtime.refresh()


async def test_refresh_returns_false_on_failed_without_username(
    hass: HomeAssistant,
) -> None:
    """API-key-only entries surface EcobeeAuthFailedError as a False return, no raise."""
    entry = _api_key_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.side_effect = EcobeeAuthFailedError("bad pw")
        ecobee.config = {ECOBEE_API_KEY: "test-api-key"}  # no username

        runtime = EcobeeData(hass, entry, api_key="test-api-key", refresh_token="rt")
        assert await runtime.refresh() is False


async def test_refresh_returns_false_on_unknown_error(hass: HomeAssistant) -> None:
    """Refresh returns False on EcobeeAuthUnknownError."""
    entry = _api_key_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.side_effect = EcobeeAuthUnknownError("network")

        runtime = EcobeeData(hass, entry, api_key="test-api-key", refresh_token="rt")
        assert await runtime.refresh() is False


async def test_refresh_returns_false_when_refresh_tokens_returns_false(
    hass: HomeAssistant,
) -> None:
    """A False return from pyecobee.refresh_tokens surfaces as False from EcobeeData."""
    entry = _api_key_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.return_value = False

        runtime = EcobeeData(hass, entry, api_key="test-api-key", refresh_token="rt")
        assert await runtime.refresh() is False


async def test_refresh_updates_entry_with_api_key_and_token(
    hass: HomeAssistant,
) -> None:
    """A successful refresh on an API-key entry stores api_key + refresh_token."""
    entry = _api_key_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.return_value = True
        ecobee.config = {
            ECOBEE_API_KEY: "test-api-key",
            ECOBEE_REFRESH_TOKEN: "fresh-rt",
        }

        runtime = EcobeeData(
            hass, entry, api_key="test-api-key", refresh_token="old-rt"
        )
        assert await runtime.refresh() is True

    assert entry.data == {
        CONF_API_KEY: "test-api-key",
        CONF_REFRESH_TOKEN: "fresh-rt",
    }


async def test_refresh_updates_entry_with_username_password(
    hass: HomeAssistant,
) -> None:
    """A successful refresh on a credentials entry preserves username/password."""
    entry = _credentials_entry(hass)
    with patch("homeassistant.components.ecobee.Ecobee") as mock_ecobee_cls:
        ecobee = mock_ecobee_cls.return_value
        ecobee.refresh_tokens.return_value = True
        ecobee.config = {
            ECOBEE_USERNAME: "user@example.com",
            ECOBEE_PASSWORD: "pw",
            ECOBEE_REFRESH_TOKEN: "fresh-rt",
        }

        runtime = EcobeeData(
            hass,
            entry,
            username="user@example.com",
            password="pw",
            refresh_token="old-rt",
        )
        assert await runtime.refresh() is True

    assert entry.data == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "pw",
        CONF_REFRESH_TOKEN: "fresh-rt",
    }

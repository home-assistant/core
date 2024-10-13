"""Test the Opower config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from opower import CannotConnect, InvalidAuth
import pytest

from homeassistant import config_entries
from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True, name="mock_setup_entry")
def override_async_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opower.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock]:
    """Mock unloading a config entry."""
    with patch(
        "homeassistant.components.opower.async_unload_entry",
        return_value=True,
    ) as mock_unload_entry:
        yield mock_unload_entry


async def test_form(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "utility": "Pacific Gas and Electric Company (PG&E)",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Pacific Gas and Electric Company (PG&E) (test-username)"
    assert result2["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_with_mfa(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "utility": "Consolidated Edison (ConEd)",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert not result2["errors"]

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "totp_secret": "test-totp",
            },
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Consolidated Edison (ConEd) (test-username)"
    assert result3["data"] == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "test-password",
        "totp_secret": "test-totp",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_with_mfa_bad_secret(
    recorder_mock: Recorder, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test MFA asks for password again when validation fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "utility": "Consolidated Edison (ConEd)",
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert not result2["errors"]

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=InvalidAuth,
    ) as mock_login:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "totp_secret": "test-totp",
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {
        "base": "invalid_auth",
    }

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "updated-password",
                "totp_secret": "updated-totp",
            },
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Consolidated Edison (ConEd) (test-username)"
    assert result4["data"] == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "updated-password",
        "totp_secret": "updated-totp",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


@pytest.mark.parametrize(
    ("api_exception", "expected_error"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    recorder_mock: Recorder, hass: HomeAssistant, api_exception, expected_error
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
        side_effect=api_exception,
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "utility": "Pacific Gas and Electric Company (PG&E)",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}
    assert mock_login.call_count == 1


async def test_form_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user input for config_entry that already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "utility": "Pacific Gas and Electric Company (PG&E)",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert mock_login.call_count == 0


async def test_form_not_already_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user input for config_entry different than the existing one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "utility": "Pacific Gas and Electric Company (PG&E)",
                "username": "test-username2",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result2["title"] == "Pacific Gas and Electric Company (PG&E) (test-username2)"
    )
    assert result2["data"] == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username2",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 2
    assert mock_login.call_count == 1


async def test_form_valid_reauth(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we can handle a valid reauth."""
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["title_placeholders"] == {"name": mock_config_entry.title}

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password2"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    assert mock_config_entry.data == {
        "utility": "Pacific Gas and Electric Company (PG&E)",
        "username": "test-username",
        "password": "test-password2",
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1


async def test_form_valid_reauth_with_mfa(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we can handle a valid reauth."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            # Requires MFA
            "utility": "Consolidated Edison (ConEd)",
        },
    )
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]

    with patch(
        "homeassistant.components.opower.config_flow.Opower.async_login",
    ) as mock_login:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password2",
                "totp_secret": "test-totp",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    await hass.async_block_till_done()
    assert mock_config_entry.data == {
        "utility": "Consolidated Edison (ConEd)",
        "username": "test-username",
        "password": "test-password2",
        "totp_secret": "test-totp",
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_login.call_count == 1

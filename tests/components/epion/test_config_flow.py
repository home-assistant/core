"""Tests for the Epion config flow."""

from unittest.mock import MagicMock, patch

from epion import EpionAuthenticationError, EpionConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.epion.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_KEY = "test-key-123"
NEW_API_KEY = "new-key-456"
ACCOUNT_ID = "account-dupe-123"


async def test_user_flow(hass: HomeAssistant, mock_epion: MagicMock) -> None:
    """Test we can handle a regular successflow setup flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert result["result"].unique_id == "account-dupe-123"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EpionAuthenticationError("Invalid auth"), "invalid_auth"),
        (EpionConnectionError("Timeout error"), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant, exception: Exception, error: str, mock_epion: MagicMock
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_epion.return_value.get_current.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_epion.return_value.get_current.side_effect = None

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant, mock_epion: MagicMock) -> None:
    """Test duplicate setup handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
        },
        unique_id="account-dupe-123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(hass: HomeAssistant, mock_epion: MagicMock) -> None:
    """Test reauthentication updates the API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=ACCOUNT_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: NEW_API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_API_KEY: NEW_API_KEY}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            EpionAuthenticationError("Invalid auth"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            EpionConnectionError("Timeout error"), "cannot_connect", id="cannot_connect"
        ),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant, exception: Exception, error: str, mock_epion: MagicMock
) -> None:
    """Test reauthentication errors and recovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=ACCOUNT_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_epion.return_value.get_current.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: NEW_API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_epion.return_value.get_current.side_effect = None

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: NEW_API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_API_KEY: NEW_API_KEY}


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant, mock_epion: MagicMock
) -> None:
    """Test reauthentication with an API key of a different account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id="other-account-456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: NEW_API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == {CONF_API_KEY: API_KEY}

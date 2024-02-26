"""Test the fyta config flow."""
from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.fyta.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USERNAME = "fyta_user"
PASSWORD = "fyta_pass"
ACCESS_TOKEN = "123xyz"
EXPIRATION = datetime.now()


@pytest.fixture
def mock_fyta():
    """Build a fixture for the Fyta API that connects successfully and returns one device."""

    mock_fyta_api = AsyncMock()
    with patch(
        "homeassistant.components.fyta.config_flow.FytaConnector",
        return_value=mock_fyta_api,
    ) as mock_fyta_api:
        mock_fyta_api.return_value.login.return_value = {
            "access_token": ACCESS_TOKEN,
            "expiration": EXPIRATION,
        }
        yield mock_fyta_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fyta.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_user_flow(
    hass: HomeAssistant, mock_fyta: AsyncMock, mock_setup_entry
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == USERNAME
    assert result2["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FytaConnectionError, {"base": "cannot_connect"}),
        (FytaAuthentificationError, {"base": "invalid_auth"}),
        (FytaPasswordError, {"base": "invalid_auth", CONF_PASSWORD: "password_error"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: dict[str, str],
    mock_fyta: AsyncMock,
    mock_setup_entry,
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_fyta.return_value.login.side_effect = exception

    # tests with connection error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == error

    mock_fyta.return_value.login.side_effect = None

    # tests with all information provided
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD

    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test duplicate setup handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id="fyta_unique_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fyta.config_flow.FytaConnector",
        return_value=AsyncMock(),
    ) as mock:
        fyta = mock.return_value
        fyta.login.return_value = {
            "access_token": ACCESS_TOKEN,
            "expiration": EXPIRATION,
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

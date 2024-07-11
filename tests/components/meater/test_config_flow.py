"""Define tests for the Meater config flow."""

from unittest.mock import AsyncMock, patch

from meater import AuthenticationError, ServiceUnavailableError
import pytest

from homeassistant import config_entries
from homeassistant.components.meater import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_client():
    """Define a fixture for authentication coroutine."""
    return AsyncMock(return_value=None)


@pytest.fixture
def mock_meater(mock_client):
    """Mock the meater library."""
    with patch("homeassistant.components.meater.MeaterApi.authenticate") as mock_:
        mock_.side_effect = mock_client
        yield mock_


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("mock_client", [AsyncMock(side_effect=Exception)])
async def test_unknown_auth_error(hass: HomeAssistant, mock_meater) -> None:
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )
    assert result["errors"] == {"base": "unknown_auth_error"}


@pytest.mark.parametrize("mock_client", [AsyncMock(side_effect=AuthenticationError)])
async def test_invalid_credentials(hass: HomeAssistant, mock_meater) -> None:
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "mock_client", [AsyncMock(side_effect=ServiceUnavailableError)]
)
async def test_service_unavailable(hass: HomeAssistant, mock_meater) -> None:
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
    )
    assert result["errors"] == {"base": "service_unavailable_error"}


async def test_user_flow(hass: HomeAssistant, mock_meater) -> None:
    """Test that the user flow works."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.meater.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], conf)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }


async def test_reauth_flow(hass: HomeAssistant, mock_meater) -> None:
    """Test that the reauth flow works."""
    data = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@host.com",
        data=data,
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data=data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "passwordabc"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "passwordabc",
    }

"""Test the Pterodactyl config flow."""

from pydactyl import PterodactylClient
from pydactyl.exceptions import BadRequestError, PterodactylApiError
import pytest
from requests.exceptions import HTTPError
from requests.models import Response

from homeassistant.components.pterodactyl.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_API_KEY, TEST_URL, TEST_USER_INPUT

from tests.common import MockConfigEntry


def mock_response():
    """Mock HTTP response."""
    mock = Response()
    mock.status_code = 401

    return mock


@pytest.mark.usefixtures("mock_pterodactyl", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test full flow without errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_URL
    assert result["data"] == TEST_USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (PterodactylApiError, "cannot_connect"),
        (BadRequestError, "cannot_connect"),
        (Exception, "unknown"),
        (HTTPError(response=mock_response()), "invalid_auth"),
    ],
)
async def test_recovery_after_error(
    hass: HomeAssistant,
    exception_type: Exception,
    expected_error: str,
    mock_pterodactyl: PterodactylClient,
) -> None:
    """Test recovery after an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pterodactyl.client.servers.list_servers.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input=TEST_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pterodactyl.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input=TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_URL
    assert result["data"] == TEST_USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_pterodactyl")
async def test_service_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow abort if the Pterodactyl server is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pterodactyl", "mock_setup_entry")
async def test_reauth_full_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth config flow success."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_URL] == TEST_URL
    assert mock_config_entry.data[CONF_API_KEY] == TEST_API_KEY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception_type", "expected_error"),
    [
        (PterodactylApiError, "cannot_connect"),
        (BadRequestError, "cannot_connect"),
        (Exception, "unknown"),
        (HTTPError(response=mock_response()), "invalid_auth"),
    ],
)
async def test_reauth_recovery_after_error(
    hass: HomeAssistant,
    exception_type: Exception,
    expected_error: str,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: PterodactylClient,
) -> None:
    """Test recovery after an error during re-authentication."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_pterodactyl.client.servers.list_servers.side_effect = exception_type

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pterodactyl.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: TEST_API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_URL] == TEST_URL
    assert mock_config_entry.data[CONF_API_KEY] == TEST_API_KEY

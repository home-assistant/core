"""Test the ViCare config flow."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components.vicare.const import CONF_HEATING_TYPE, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import MOCK_MAC

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

TOKEN_URL = "https://iam.viessmann-climatesolutions.com/idp/v3/token"

DHCP_INFO = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="mock_hostname",
    macaddress=MOCK_MAC.lower().replace(":", ""),
)


async def _do_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    result: dict,
) -> dict:
    """Complete the OAuth2 flow from EXTERNAL_STEP to the next step."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the full OAuth2 flow with heating type selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await _do_oauth_flow(hass, hass_client_no_auth, aioclient_mock, result)

    # After OAuth, should ask for heating type
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "heating_type"

    # Submit heating type
    with patch("homeassistant.components.vicare.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HEATING_TYPE: "auto"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ViCare"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["token"]["access_token"] == "mock-access-token"
    assert result["data"][CONF_HEATING_TYPE] == "auto"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # User confirms, gets redirected to OAuth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    result = await _do_oauth_flow(hass, hass_client_no_auth, aioclient_mock, result)

    # Should update existing entry
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_preserves_existing_data(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth preserves heating_type and other non-OAuth data."""
    mock_config_entry.add_to_hass(hass)

    # Verify original data has heating_type
    assert mock_config_entry.data[CONF_HEATING_TYPE] == "auto"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await _do_oauth_flow(hass, hass_client_no_auth, aioclient_mock, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Verify heating_type is preserved and token is updated
    assert mock_config_entry.data[CONF_HEATING_TYPE] == "auto"
    assert mock_config_entry.data["token"]["access_token"] == "mock-access-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_dhcp_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we can setup from DHCP discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_INFO,
    )

    result = await _do_oauth_flow(hass, hass_client_no_auth, aioclient_mock, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "heating_type"

    with patch("homeassistant.components.vicare.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HEATING_TYPE: "auto"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ViCare"


async def test_dhcp_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": {"access_token": "test"}},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_input_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ViCare",
        data={"auth_implementation": DOMAIN, "token": {"access_token": "test"}},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

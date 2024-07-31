"""Test the Weheat config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.weheat.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    HEAT_PUMP_INFO,
    NO_PUMP_FOUND,
    SELECT_PUMP_OPTION,
    SINGLE_PUMP_FOUND,
    TWO_PUMPS_FOUND,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> None:
    """Check full of adding a single heat pump."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await handle_oath(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.weheat.config_flow.HeatPumpDiscovery"
        ) as mock_weheat,
    ):
        mock_weheat.discover.return_value = SINGLE_PUMP_FOUND
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_weheat.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_devices_available(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> None:
    """Check flow abort when no devices are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await handle_oath(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.weheat.config_flow.HeatPumpDiscovery"
        ) as mock_weheat,
    ):
        mock_weheat.discover.return_value = NO_PUMP_FOUND
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_weheat.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_two_or_more_devices(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> None:
    """Check flow presenting a selection when two or more devices are available."""
    result = await authenticate_and_provide_two_pumps(
        hass, hass_client_no_auth, aioclient_mock
    )

    assert result["data_schema"].schema.get("uuid") is not None
    assert len(result["data_schema"].schema.get("uuid").container) == 2
    # check that both heat pumps are in the option list
    assert TWO_PUMPS_FOUND[0].uuid in result["data_schema"].schema.get("uuid").container
    assert TWO_PUMPS_FOUND[1].uuid in result["data_schema"].schema.get("uuid").container


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize("selected_pump", SELECT_PUMP_OPTION)
async def test_two_or_more_devices_correct_selection(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    selected_pump,
    setup_credentials,
) -> None:
    """Check that the correct pump is selected when having two options."""
    result = await authenticate_and_provide_two_pumps(
        hass, hass_client_no_auth, aioclient_mock
    )

    user_input = {"uuid": TWO_PUMPS_FOUND[selected_pump].uuid}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TWO_PUMPS_FOUND[selected_pump].uuid
    assert result["result"].data["heat_pump_info"] == TWO_PUMPS_FOUND[selected_pump]


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_data_retention(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> None:
    """Check reauth flow and that it keeps the data of the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SINGLE_PUMP_FOUND[0].uuid,
        data={HEAT_PUMP_INFO: SINGLE_PUMP_FOUND[0]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await handle_oath(hass, hass_client_no_auth, aioclient_mock, result)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert entry.data.get(HEAT_PUMP_INFO) == SINGLE_PUMP_FOUND[0]


async def authenticate_and_provide_two_pumps(hass, hass_client_no_auth, aioclient_mock):
    """Handle oath and provide two pumps for selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await handle_oath(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.weheat.config_flow.HeatPumpDiscovery"
        ) as mock_weheat,
    ):
        mock_weheat.discover.return_value = TWO_PUMPS_FOUND
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_weheat.mock_calls) == 1
    return result


async def handle_oath(hass, hass_client_no_auth, aioclient_mock, result):
    """Handle the Oauth2 part of the flow."""
    state = config_entry_oauth2_flow._encode_jwt(  # noqa: SLF001
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

"""Test the Famn config flow."""

import asyncio
from unittest.mock import AsyncMock

from famn_sdk import ApiError, DeviceTokenResponse, StartDevicePairingResponse
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.famn.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from .conftest import DEVICE_ID, PAIRING_SECRET, SPACE_ID

from tests.common import MockConfigEntry, load_json_object_fixture

pytestmark = [pytest.mark.usefixtures("mock_setup_entry", "mock_device_api")]

PLACEHOLDERS = {
    "code": "ABCD-EFGH",
    "pairing_id": "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5001",
    "url": "https://famn.app/link?p=2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5001",
}


async def _start_flow(hass: HomeAssistant) -> FlowResult:
    """Start the user flow and check that it shows the QR form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == PLACEHOLDERS
    assert "qr_code" in result["data_schema"].schema
    return result


async def _submit_and_approve(
    hass: HomeAssistant, result: FlowResult, pairing_approved: asyncio.Event
) -> FlowResult:
    """Submit the QR form, approve the pairing and run the flow to its end."""
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    pairing_approved.set()
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_full_flow(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
) -> None:
    """Test pairing Home Assistant with Famn."""
    result = await _start_flow(hass)

    # The QR encodes the deep link with the embedded pairing secret.
    qr_selector = result["data_schema"].schema["qr_code"]
    assert qr_selector.config["data"] == (
        "https://famn.app/link?p=2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5001"
        f"&s={PAIRING_SECRET}"
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "wait"
    assert result["description_placeholders"] == PLACEHOLDERS

    pairing_approved.set()
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant"
    assert result["result"].unique_id == SPACE_ID
    assert result["data"] == {
        CONF_REFRESH_TOKEN: "mock-refresh-token",
        CONF_DEVICE_ID: DEVICE_ID,
    }

    # The pairing secret parsed from the QR deep link is sent when polling.
    poll_body = mock_device_api.poll_device_pairing_endpoint.call_args.kwargs["body"]
    assert poll_body.pairing_secret == PAIRING_SECRET


async def test_approved_before_submit(
    hass: HomeAssistant, pairing_approved: asyncio.Event
) -> None:
    """Test the flow finishes right away when approved while the QR is shown."""
    result = await _start_flow(hass)

    # The background poll finishes while the user is still on the form.
    pairing_approved.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_start_pairing_error(
    hass: HomeAssistant, mock_device_api: AsyncMock
) -> None:
    """Test the flow aborts when the pairing session cannot be started."""
    mock_device_api.start_device_pairing_endpoint.side_effect = ApiError(500, "boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_missing_pairing_secret(
    hass: HomeAssistant, mock_device_api: AsyncMock
) -> None:
    """Test the flow aborts when the pairing response contains no secret."""
    pairing = load_json_object_fixture("pairing.json", DOMAIN)
    pairing["qrUrl"] = pairing["verificationUrl"]
    mock_device_api.start_device_pairing_endpoint.return_value = (
        StartDevicePairingResponse.from_dict(pairing)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize("status", [401, 404, 410])
async def test_pairing_gone(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
    status: int,
) -> None:
    """Test the flow aborts when the pairing is gone or expired server-side."""

    async def _poll(**kwargs: object) -> DeviceTokenResponse:
        await pairing_approved.wait()
        raise ApiError(status, "gone")

    mock_device_api.poll_device_pairing_endpoint.side_effect = _poll

    result = await _start_flow(hass)
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "pairing_timeout"


async def test_pairing_timeout(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the flow aborts when the user does not approve the code in time."""
    freezer.move_to("2026-08-12T12:06:00Z")
    mock_device_api.pairing_result = DeviceTokenResponse(status="pending")

    result = await _start_flow(hass)
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "pairing_timeout"


async def test_incomplete_token_response(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
) -> None:
    """Test the flow rejects an approved response with missing fields."""
    mock_device_api.pairing_result = DeviceTokenResponse(
        status="approved", access_token="token-without-the-rest"
    )

    result = await _start_flow(hass)
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "pairing_timeout"


async def test_poll_transient_error_retries(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
) -> None:
    """Test that transient poll errors are retried with backoff."""
    approved = DeviceTokenResponse.from_dict(
        load_json_object_fixture("device_token.json", DOMAIN)
    )

    async def _poll(**kwargs: object) -> DeviceTokenResponse:
        await pairing_approved.wait()
        if mock_device_api.poll_device_pairing_endpoint.call_count == 1:
            raise ApiError(500, "boom")
        return approved

    mock_device_api.poll_device_pairing_endpoint.side_effect = _poll

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("homeassistant.components.famn.config_flow.POLL_BACKOFF_MAX", 0)
        result = await _start_flow(hass)
        result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_device_api.poll_device_pairing_endpoint.call_count == 2


async def test_poll_unexpected_error(
    hass: HomeAssistant,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
) -> None:
    """Test the flow aborts on an unexpected error while polling."""

    async def _poll(**kwargs: object) -> DeviceTokenResponse:
        await pairing_approved.wait()
        raise ValueError("unexpected")

    mock_device_api.poll_device_pairing_endpoint.side_effect = _poll

    result = await _start_flow(hass)
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pairing_approved: asyncio.Event,
) -> None:
    """Test that a space can only be paired once."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_flow(hass)
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pairing_approved: asyncio.Event,
) -> None:
    """Test re-pairing an existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"

    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "mock-refresh-token"


async def test_reauth_wrong_space(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    pairing_approved: asyncio.Event,
) -> None:
    """Test re-pairing against a different Famn space is rejected."""
    mock_config_entry.add_to_hass(hass)

    tokens = load_json_object_fixture("device_token.json", DOMAIN)
    tokens["device"]["relationId"] = "99999999-9999-4999-8999-999999999999"
    mock_device_api.pairing_result = DeviceTokenResponse.from_dict(tokens)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _submit_and_approve(hass, result, pairing_approved)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"

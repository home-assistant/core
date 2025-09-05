"""Tests for the EnergyID config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.energyid.const import (
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_CONFIG_DATA,
    TEST_PROVISIONING_KEY,
    TEST_PROVISIONING_SECRET,
    TEST_RECORD_NAME,
    TEST_RECORD_NUMBER,
)

from tests.common import MockConfigEntry


def strip_schema(result: dict) -> dict:
    """Remove data_schema from a flow result for snapshot testing."""
    if "data_schema" in result:
        result.pop("data_schema")
    return result


async def test_config_flow_user_step_success_claimed(
    hass: HomeAssistant,
    mock_energyid_webhook_client_class: tuple[MagicMock, MagicMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test user step success when the device is already claimed."""
    _, mock_flow_client = mock_energyid_webhook_client_class
    mock_flow_client.return_value.authenticate.return_value = True
    mock_flow_client.return_value.recordNumber = TEST_RECORD_NUMBER
    mock_flow_client.return_value.recordName = TEST_RECORD_NAME

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert strip_schema(result.copy()) == snapshot(name="user_step_form")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_RECORD_NAME
    assert result2["data"] == snapshot(name="create_entry_data")


@pytest.mark.parametrize(
    "mock_energyid_webhook_client_class", ["unclaimed"], indirect=True
)
async def test_config_flow_user_step_needs_claim(
    hass: HomeAssistant,
    mock_energyid_webhook_client_class: tuple[MagicMock, MagicMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test user step transitions to claim step when device is unclaimed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    # Remove 'data_schema' from both actual and expected for snapshot match
    result2_clean = result2.copy()
    result2_clean.pop("data_schema", None)
    snap = snapshot(name="auth_and_claim_step_form")
    if isinstance(snap, dict) and "data_schema" in snap:
        snap = snap.copy()
        snap.pop("data_schema")
    assert strip_schema(result2_clean) == snap
    assert result2 == snapshot(name="auth_and_claim_step_form")


@pytest.mark.parametrize(
    ("mock_energyid_webhook_client_class", "expected_error"),
    [
        (ClientError("Connection failed"), "cannot_connect"),
        (RuntimeError("Unexpected auth issue"), "unknown_auth_error"),
    ],
    indirect=["mock_energyid_webhook_client_class"],
)
async def test_config_flow_user_step_auth_errors(
    hass: HomeAssistant,
    mock_energyid_webhook_client_class: tuple[MagicMock, MagicMock],
    expected_error: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test user step with various authentication errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}
    assert result2["step_id"] == "user"


async def test_config_flow_auth_and_claim_step_success(hass: HomeAssistant) -> None:
    """Test auth_and_claim step where device becomes claimed."""
    # Start with an unclaimed client
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {
        "claim_url": "http://claim.me",
        "claim_code": "123456",
        "valid_until": "2025-12-31T23:59:59Z",
    }

    # After 'claiming', switch to a claimed client
    mock_claimed_client = MagicMock()
    mock_claimed_client.authenticate = AsyncMock(return_value=True)
    mock_claimed_client.recordNumber = TEST_RECORD_NUMBER
    mock_claimed_client.recordName = TEST_RECORD_NAME

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        side_effect=[mock_unclaimed_client, mock_claimed_client],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result_claim_form = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_claim_form["step_id"] == "auth_and_claim"

        result_create = await hass.config_entries.flow.async_configure(
            result_claim_form["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result_create["type"] is FlowResultType.CREATE_ENTRY
    assert result_create["title"] == TEST_RECORD_NAME


@pytest.mark.parametrize(
    "mock_energyid_webhook_client_class", ["unclaimed"], indirect=True
)
async def test_config_flow_auth_and_claim_step_still_unclaimed(
    hass: HomeAssistant,
    mock_energyid_webhook_client_class: tuple[MagicMock, MagicMock],
) -> None:
    """Test auth_and_claim step where device remains unclaimed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result_claim_form = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
        },
    )
    result_error = await hass.config_entries.flow.async_configure(
        result_claim_form["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result_error["type"] is FlowResultType.FORM
    assert result_error["step_id"] == "auth_and_claim"
    assert result_error["errors"] == {"base": "claim_failed_or_timed_out"}


async def test_config_flow_already_configured(
    hass: HomeAssistant,
    mock_energyid_webhook_client_class: tuple[MagicMock, MagicMock],
) -> None:
    """Test flow aborts if the unique_id is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        unique_id=TEST_RECORD_NUMBER,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"

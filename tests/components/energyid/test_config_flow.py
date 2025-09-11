"""Test EnergyID config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Test constants
TEST_PROVISIONING_KEY = "test_prov_key"
TEST_PROVISIONING_SECRET = "test_prov_secret"
TEST_RECORD_NUMBER = "site_12345"
TEST_RECORD_NAME = "My Test Site"
MAX_POLLING_ATTEMPTS = 60


async def test_config_flow_user_step_success_claimed(hass: HomeAssistant) -> None:
    """Test user step where device is already claimed."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.recordNumber = TEST_RECORD_NUMBER
    mock_client.recordName = TEST_RECORD_NAME

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_RECORD_NAME
        assert result2["data"][CONF_PROVISIONING_KEY] == TEST_PROVISIONING_KEY
        assert result2["data"][CONF_PROVISIONING_SECRET] == TEST_PROVISIONING_SECRET


@pytest.mark.parametrize("claimed", [False])
async def test_config_flow_user_step_needs_claim(
    hass: HomeAssistant, claimed: bool
) -> None:
    """Test user step where device needs to be claimed."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=claimed)
    mock_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_client,
        ),
        patch("homeassistant.components.energyid.config_flow.asyncio.sleep"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result2["type"] is FlowResultType.EXTERNAL_STEP
        assert result2["step_id"] == "auth_and_claim"


async def test_config_flow_auth_and_claim_step_success(hass: HomeAssistant) -> None:
    """Test auth_and_claim step where the device becomes claimed after polling."""
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    mock_claimed_client = MagicMock()
    mock_claimed_client.authenticate = AsyncMock(return_value=True)
    mock_claimed_client.recordNumber = TEST_RECORD_NUMBER
    mock_claimed_client.recordName = TEST_RECORD_NAME

    call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_unclaimed_client
        return mock_claimed_client

    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            side_effect=mock_webhook_client,
        ),
        patch("homeassistant.components.energyid.config_flow.asyncio.sleep"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        result_done = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert result_done["type"] is FlowResultType.EXTERNAL_STEP_DONE

        final_result = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        await hass.async_block_till_done()

        assert final_result["type"] is FlowResultType.CREATE_ENTRY
        assert final_result["title"] == TEST_RECORD_NAME


async def test_config_flow_claim_timeout(hass: HomeAssistant) -> None:
    """Test claim step when polling times out."""
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_unclaimed_client,
        ),
        patch(
            "homeassistant.components.energyid.config_flow.asyncio.sleep",
        ) as mock_sleep,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        await hass.async_block_till_done()

    assert mock_sleep.call_count == MAX_POLLING_ATTEMPTS + 1


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that already configured devices are detected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_RECORD_NUMBER,
        data={
            CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
            CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            CONF_DEVICE_ID: "existing_device",
            CONF_DEVICE_NAME: "Existing Device",
        },
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.recordNumber = TEST_RECORD_NUMBER
    mock_client.recordName = TEST_RECORD_NAME

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_config_flow_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during authentication."""
    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient.authenticate",
        side_effect=ClientError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"


async def test_config_flow_unexpected_error(hass: HomeAssistant) -> None:
    """Test unexpected error during authentication."""
    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient.authenticate",
        side_effect=Exception("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "unknown_auth_error"


async def test_config_flow_external_step_claimed_during_display(
    hass: HomeAssistant,
) -> None:
    """Test when device gets claimed while external step is being displayed."""
    call_count = 0

    def create_mock_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        mock_client = MagicMock()
        if call_count == 1:
            mock_client.authenticate = AsyncMock(return_value=False)
            mock_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}
        else:
            mock_client.authenticate = AsyncMock(return_value=True)
            mock_client.recordNumber = TEST_RECORD_NUMBER
            mock_client.recordName = TEST_RECORD_NAME
        return mock_client

    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            side_effect=create_mock_client,
        ),
        patch("homeassistant.components.energyid.config_flow.asyncio.sleep"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        result_claimed = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert result_claimed["type"] is FlowResultType.EXTERNAL_STEP_DONE

        final_result = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        await hass.async_block_till_done()

        assert final_result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_auth_and_claim_step_not_claimed(hass: HomeAssistant) -> None:
    """Test auth_and_claim step when device is not claimed after polling."""
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=False)
    mock_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}
    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_client,
        ),
        patch("homeassistant.components.energyid.config_flow.asyncio.sleep"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "x",
                CONF_PROVISIONING_SECRET: "y",
            },
        )
        # Simulate the external step
        # result3 = await hass.config_entries.flow.async_configure(result2["flow_id"])

        # Simulate the device still not being claimed
        result4 = await hass.config_entries.flow.async_configure(result2["flow_id"])
        assert result4["type"] is FlowResultType.EXTERNAL_STEP
        assert result4["step_id"] == "auth_and_claim"

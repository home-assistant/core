"""Test EnergyID config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.energyid.config_flow import EnergyIDConfigFlow
from homeassistant.components.energyid.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from homeassistant.components.energyid.energyid_sensor_mapping_flow import (
    EnergyIDSensorMappingFlowHandler,
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


@pytest.fixture(name="mock_polling_interval", autouse=True)
def mock_polling_interval_fixture() -> Generator[int]:
    """Mock polling interval to 0 for faster tests."""
    with patch(
        "homeassistant.components.energyid.config_flow.POLLING_INTERVAL", new=0
    ) as polling_interval:
        yield polling_interval


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
        assert result2["description"] == "add_sensor_mapping_hint"

        # Check unique_id is set correctly
        entry = hass.config_entries.async_get_entry(result2["result"].entry_id)
        # For initially claimed devices, unique_id should be the device_id, not record_number
        assert entry.unique_id.startswith("homeassistant_eid_")
        assert CONF_DEVICE_ID in entry.data
        assert entry.data[CONF_DEVICE_ID] == entry.unique_id


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
        assert result_external["step_id"] == "auth_and_claim"

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
        assert final_result["description"] == "add_sensor_mapping_hint"


async def test_config_flow_claim_timeout(hass: HomeAssistant) -> None:
    """Test claim step when polling times out and user continues."""
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
        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        # Simulate polling timeout, then user continuing the flow
        result_after_timeout = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        await hass.async_block_till_done()

        # After timeout, polling stops and user continues - should see external step again
        assert result_after_timeout["type"] is FlowResultType.EXTERNAL_STEP
        assert result_after_timeout["step_id"] == "auth_and_claim"

        # Verify polling actually ran the expected number of times
        # Sleep happens at beginning of polling loop, so MAX_POLLING_ATTEMPTS + 1 sleeps
        # but only MAX_POLLING_ATTEMPTS authentication attempts
        assert mock_sleep.call_count == MAX_POLLING_ATTEMPTS + 1


async def test_duplicate_unique_id_prevented(hass: HomeAssistant) -> None:
    """Test that duplicate device_id (unique_id) is detected and aborted."""
    # Create existing entry with a specific device_id as unique_id
    # The generated device_id format is: homeassistant_eid_{instance_id}_{timestamp_ms}
    # With instance_id="test_instance" and time=123.0, this becomes:
    # homeassistant_eid_test_instance_123000
    existing_device_id = "homeassistant_eid_test_instance_123000"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=existing_device_id,
        data={
            CONF_PROVISIONING_KEY: "old_key",
            CONF_PROVISIONING_SECRET: "old_secret",
            CONF_DEVICE_ID: existing_device_id,
            CONF_DEVICE_NAME: "Existing Device",
        },
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.recordNumber = TEST_RECORD_NUMBER
    mock_client.recordName = TEST_RECORD_NAME

    # Mock to return the same device_id that already exists
    with (
        patch(
            "homeassistant.components.energyid.config_flow.WebhookClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.energyid.config_flow.async_get_instance_id",
            return_value="test_instance",
        ),
        patch(
            "homeassistant.components.energyid.config_flow.asyncio.get_event_loop"
        ) as mock_loop,
    ):
        # Force the same device_id to be generated
        mock_loop.return_value.time.return_value = 123.0

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

        # Should abort because unique_id (device_id) already exists
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_multiple_different_devices_allowed(hass: HomeAssistant) -> None:
    """Test that multiple config entries with different device_ids are allowed."""
    # Create existing entry with one device_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="homeassistant_eid_device_1",
        data={
            CONF_PROVISIONING_KEY: "key1",
            CONF_PROVISIONING_SECRET: "secret1",
            CONF_DEVICE_ID: "homeassistant_eid_device_1",
            CONF_DEVICE_NAME: "Device 1",
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
        # Check initial result
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Configure with different credentials (will create different device_id)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "key2",
                CONF_PROVISIONING_SECRET: "secret2",
            },
        )

        # Should succeed because device_id will be different
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_RECORD_NAME
        assert result2["data"][CONF_PROVISIONING_KEY] == "key2"
        assert result2["data"][CONF_PROVISIONING_SECRET] == "secret2"
        assert result2["description"] == "add_sensor_mapping_hint"

        # Verify unique_id is set
        new_entry = hass.config_entries.async_get_entry(result2["result"].entry_id)
        assert new_entry.unique_id is not None
        assert new_entry.unique_id != entry.unique_id  # Different from first entry


async def test_config_flow_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during authentication."""
    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient.authenticate",
        side_effect=ClientError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        side_effect=create_mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        # User continues immediately - device is claimed, polling task should be cancelled
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
    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "x",
                CONF_PROVISIONING_SECRET: "y",
            },
        )
        assert result2["type"] is FlowResultType.EXTERNAL_STEP

        # User continues immediately - device still not claimed, polling task should be cancelled
        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"])
        assert result3["type"] is FlowResultType.EXTERNAL_STEP
        assert result3["step_id"] == "auth_and_claim"


async def test_config_flow_reauth_success(
    hass: HomeAssistant,
) -> None:
    """Test the reauthentication flow for EnergyID integration (success path)."""
    # Existing config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="site_12345",
        data={
            CONF_PROVISIONING_KEY: "old_key",
            CONF_PROVISIONING_SECRET: "old_secret",
            CONF_DEVICE_ID: "existing_device",
            CONF_DEVICE_NAME: "Existing Device",
        },
    )
    entry.add_to_hass(hass)

    # Mock client for successful reauth
    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.recordNumber = "site_12345"
    mock_client.recordName = "My Test Site"

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        # Start reauth flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

        # Submit new credentials
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "new_key",
                CONF_PROVISIONING_SECRET: "new_secret",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.ABORT
        # Entry should be updated
        updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
        assert updated_entry.data[CONF_PROVISIONING_KEY] == "new_key"
        assert updated_entry.data[CONF_PROVISIONING_SECRET] == "new_secret"


@pytest.mark.parametrize(
    ("auth_status", "auth_message", "expected_error"),
    [
        (401, "Unauthorized", "invalid_auth"),
        (500, "Server Error", "cannot_connect"),
    ],
)
async def test_config_flow_client_response_error(
    hass: HomeAssistant,
    auth_status: int,
    auth_message: str,
    expected_error: str,
) -> None:
    """Test config flow with ClientResponseError."""
    mock_client = MagicMock()
    mock_client.authenticate.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=auth_status,
        message=auth_message,
    )

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == expected_error


async def test_config_flow_reauth_needs_claim(hass: HomeAssistant) -> None:
    """Test reauth flow when device needs to be claimed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="site_12345",
        data={
            CONF_PROVISIONING_KEY: "old_key",
            CONF_PROVISIONING_SECRET: "old_secret",
            CONF_DEVICE_ID: "existing_device",
            CONF_DEVICE_NAME: "Existing Device",
        },
    )
    entry.add_to_hass(hass)

    # Mock client that needs claiming
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
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        # Check initial reauth form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "new_key",
                CONF_PROVISIONING_SECRET: "new_secret",
            },
        )

        assert result2["type"] is FlowResultType.EXTERNAL_STEP
        assert result2["step_id"] == "auth_and_claim"


async def test_async_get_supported_subentry_types(hass: HomeAssistant) -> None:
    """Test async_get_supported_subentry_types returns correct types."""

    mock_entry = MockConfigEntry(domain=DOMAIN, data={})

    result = EnergyIDConfigFlow.async_get_supported_subentry_types(mock_entry)

    assert "sensor_mapping" in result
    assert result["sensor_mapping"] == EnergyIDSensorMappingFlowHandler


async def test_polling_stops_on_invalid_auth_error(hass: HomeAssistant) -> None:
    """Test that polling stops when invalid_auth error occurs during auth_and_claim polling."""
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    mock_error_client = MagicMock()
    mock_error_client.authenticate = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
        )
    )

    call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_unclaimed_client if call_count == 1 else mock_error_client

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        assert result_done["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()


async def test_polling_stops_on_cannot_connect_error(hass: HomeAssistant) -> None:
    """Test that polling stops when cannot_connect error occurs during auth_and_claim polling."""
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    mock_error_client = MagicMock()
    mock_error_client.authenticate = AsyncMock(
        side_effect=ClientError("Connection failed")
    )

    call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_unclaimed_client if call_count == 1 else mock_error_client

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        assert result_done["type"] is FlowResultType.EXTERNAL_STEP
        await hass.async_block_till_done()


async def test_auth_and_claim_subsequent_auth_error(hass: HomeAssistant) -> None:
    """Test that auth_and_claim step handles authentication errors during polling attempts."""
    mock_unclaimed_client = MagicMock()
    mock_unclaimed_client.authenticate = AsyncMock(return_value=False)
    mock_unclaimed_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}

    mock_error_client = MagicMock()
    mock_error_client.authenticate = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
        )
    )

    call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_unclaimed_client if call_count <= 2 else mock_error_client

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        assert result_done["type"] is FlowResultType.EXTERNAL_STEP

        final_result = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert final_result["type"] is FlowResultType.EXTERNAL_STEP
        assert final_result["step_id"] == "auth_and_claim"


async def test_reauth_with_error(hass: HomeAssistant) -> None:
    """Test that reauth flow shows error when authentication fails with 401."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PROVISIONING_KEY: "old_key",
            CONF_PROVISIONING_SECRET: "old_secret",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DEVICE_NAME: "test_device_name",
        },
    )
    mock_entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.authenticate = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
        )
    )

    with patch(
        "homeassistant.components.energyid.config_flow.WebhookClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_entry.entry_id,
            },
            data=mock_entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: "new_key",
                CONF_PROVISIONING_SECRET: "new_secret",
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_auth"


async def test_polling_cancellation_on_auth_failure(hass: HomeAssistant) -> None:
    """Test that polling is cancelled when authentication fails during auth_and_claim."""
    call_count = 0
    auth_call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First client for initial claimless auth
            mock_client = MagicMock()
            mock_client.authenticate = AsyncMock(return_value=False)
            mock_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}
            return mock_client
        # Subsequent client for polling check - fails authentication
        mock_client = MagicMock()

        async def auth_with_error():
            nonlocal auth_call_count
            auth_call_count += 1
            raise ClientError("Connection failed")

        mock_client.authenticate = auth_with_error
        return mock_client

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Start auth_and_claim flow - sets up polling
        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        # Wait for polling task to encounter the error and stop
        await hass.async_block_till_done()

        # Verify polling stopped after the error
        # auth_call_count should be 1 (one failed attempt during polling)
        initial_auth_count = auth_call_count
        assert initial_auth_count == 1

        # Trigger user continuing the flow - polling should already be stopped
        result_failed = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert result_failed["type"] is FlowResultType.EXTERNAL_STEP
        assert result_failed["step_id"] == "auth_and_claim"

        # Wait a bit and verify no further authentication attempts occurred
        await hass.async_block_till_done()
        assert (
            auth_call_count == initial_auth_count + 1
        )  # One more for the manual check


async def test_polling_cancellation_on_success(hass: HomeAssistant) -> None:
    """Test that polling is cancelled when device becomes claimed successfully during auth_and_claim."""
    call_count = 0
    auth_call_count = 0

    def mock_webhook_client(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First client for initial claimless auth
            mock_client = MagicMock()
            mock_client.authenticate = AsyncMock(return_value=False)
            mock_client.get_claim_info.return_value = {"claim_url": "http://claim.me"}
            return mock_client
        # Subsequent client for polling check - device now claimed
        mock_client = MagicMock()

        async def auth_success():
            nonlocal auth_call_count
            auth_call_count += 1
            return True

        mock_client.authenticate = auth_success
        mock_client.recordNumber = TEST_RECORD_NUMBER
        mock_client.recordName = TEST_RECORD_NAME
        return mock_client

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
        # Check initial form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Start auth_and_claim flow - sets up polling task
        result_external = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PROVISIONING_KEY: TEST_PROVISIONING_KEY,
                CONF_PROVISIONING_SECRET: TEST_PROVISIONING_SECRET,
            },
        )
        assert result_external["type"] is FlowResultType.EXTERNAL_STEP

        # Wait for polling to detect the device is claimed and advance the flow
        await hass.async_block_till_done()

        # Verify polling made authentication attempt
        # auth_call_count should be 1 (polling detected device is claimed)
        assert auth_call_count >= 1
        claimed_auth_count = auth_call_count

        # User continues - device is already claimed, polling should be cancelled
        result_done = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert result_done["type"] is FlowResultType.EXTERNAL_STEP_DONE

        # Verify polling was cancelled - the auth count should only increase by 1
        # (for the manual check when user continues, not from polling)
        assert auth_call_count == claimed_auth_count + 1

        # Final call to create entry
        final_result = await hass.config_entries.flow.async_configure(
            result_external["flow_id"]
        )
        assert final_result["type"] is FlowResultType.CREATE_ENTRY

        # Wait a bit and verify no further authentication attempts from polling
        await hass.async_block_till_done()
        final_auth_count = auth_call_count

        # Ensure all background tasks have completed and polling really stopped
        await hass.async_block_till_done()

        # No new auth attempts should have occurred (polling was cancelled)
        assert auth_call_count == final_auth_count

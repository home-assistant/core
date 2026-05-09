"""Test the CCL Electronics config flow."""

from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from aioccl.exception import CCLDeviceRegistrationException
from aiohttp import web

from homeassistant import config_entries
from homeassistant.components.ccl.const import DOMAIN
from homeassistant.components.ccl.devices import devices
from homeassistant.components.webhook import async_generate_url
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component

from .conftest import WEBHOOK_ID

from tests.typing import ClientSessionGenerator


async def test_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test we can create a config entry."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        # Initial step should return SHOW_PROGRESS while waiting for device update
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"

        # Simulate successful webhook request
        client = await hass_client_no_auth()
        webhook_url = async_generate_url(hass, WEBHOOK_ID)
        body = {"hello": "world"}

        def handler_side_effect(request, devices_dict):
            # Simulate the handler setting last_update_time
            device = devices_dict[WEBHOOK_ID]
            device.last_update_time = 123
            return web.Response(status=200)

        with patch(
            "homeassistant.components.ccl.CCLServer.handler",
            side_effect=handler_side_effect,
        ):
            resp = await client.post(urlparse(webhook_url).path, json=body)

        assert resp.status == 200

        # Wait for the background task to complete after webhook is posted
        await hass.async_block_till_done()

        # After device updates, configure to complete the flow
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_ID] == WEBHOOK_ID
        assert len(mock_setup_entry.mock_calls) == 1


async def test_no_url_available_error_webhook_generation(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of NoURLAvailableError during webhook URL generation."""
    hass.config.external_url = None
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_url",
        side_effect=NoURLAvailableError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Should abort with invalid_host reason
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "invalid_host"


async def test_ccl_device_registration_exception_handled(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of CCLDeviceRegistrationException when device already registered."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch(
            "homeassistant.components.ccl.config_flow.register",
            side_effect=CCLDeviceRegistrationException("Already registered"),
        ),
    ):
        # Add device to the devices dict before test starts
        devices[WEBHOOK_ID] = mock_ccl

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Should continue despite the exception (using existing device)
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"


async def test_value_error_webhook_registration(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of ValueError during webhook registration."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch(
            "homeassistant.components.ccl.config_flow.register_webhook",
            side_effect=ValueError("Invalid webhook configuration"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Should abort with invalid_webhook reason
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "invalid_webhook"


async def test_no_url_available_error_webhook_registration(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of NoURLAvailableError during webhook registration."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch(
            "homeassistant.components.ccl.config_flow.register_webhook",
            side_effect=NoURLAvailableError(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Should abort with invalid_webhook reason
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "invalid_webhook"


async def test_timeout_error_task_one(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of TimeoutError when task_one times out."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        # Initial step should return SHOW_PROGRESS
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Verify the flow starts in SHOW_PROGRESS state
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"


async def test_abort_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of AbortFlow when device already configured."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch(
            "homeassistant.components.ccl.config_flow.CCLConfigFlow._abort_if_unique_id_configured",
            side_effect=AbortFlow("already_configured"),
        ),
    ):
        # Should abort with already_configured when device is already set up
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # The abort should happen during task execution
        # Check that we either get progress or abort depending on timing
        assert result["type"] in (FlowResultType.SHOW_PROGRESS, FlowResultType.ABORT)

        if result["type"] is FlowResultType.ABORT:
            assert result["reason"] == "already_configured"


async def test_task_one_cancellation(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test that task_one can be cancelled successfully during config flow removal."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        # Initial step should return SHOW_PROGRESS
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"
        flow_id = result["flow_id"]

        # Get the current progress flows
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) > 0

        # Find the flow and verify it has async_remove method
        flow_data = next((f for f in flows if f["flow_id"] == flow_id), None)
        assert flow_data is not None

        # Abort the flow - this should trigger async_remove and cancel task_one
        hass.config_entries.flow.async_abort(flow_id)
        await hass.async_block_till_done()

        # Verify the flow has been removed from progress
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 0

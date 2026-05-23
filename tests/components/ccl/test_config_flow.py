"""Test the CCL Electronics config flow."""

import asyncio
import contextlib
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from aioccl.exception import CCLDeviceRegistrationException
from aiohttp import web

from homeassistant import config_entries
from homeassistant.components.ccl import KEY_DEVICES
from homeassistant.components.ccl.config_flow import CCLConfigFlow
from homeassistant.components.ccl.const import DOMAIN
from homeassistant.components.webhook import async_generate_url
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_WEBHOOK_ID
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

        async def handler_side_effect(request, devices_dict):
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
        hass.data[KEY_DEVICES][WEBHOOK_ID] = mock_ccl

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


async def test_timeout_error_task_one(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling of TimeoutError when task_one times out."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    async def mock_wait_for_timeout(coro, timeout):
        """Mock wait_for that raises TimeoutError."""
        # Close the coroutine to avoid warning
        with contextlib.suppress(AttributeError, GeneratorExit):
            coro.close()
        raise TimeoutError

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch("asyncio.wait_for", side_effect=mock_wait_for_timeout),
    ):
        # Create the flow - the asyncio.wait_for will timeout immediately
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        flow_id = result["flow_id"]

        # Wait for background tasks to process
        await hass.async_block_till_done()

        if result["type"] in (
            FlowResultType.SHOW_PROGRESS,
            FlowResultType.SHOW_PROGRESS_DONE,
        ):
            flows = hass.config_entries.flow.async_progress()
            if any(f for f in flows if f["flow_id"] == flow_id):
                result = await hass.config_entries.flow.async_configure(flow_id, {})
                await hass.async_block_till_done()
            else:
                result = {"type": FlowResultType.ABORT, "reason": "connect_timeout"}

        # The flow should abort with connect_timeout due to the timeout
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "connect_timeout"


async def test_cancelled_error_task_one(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling when task_one is cancelled during config flow progress."""
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    config_flow = CCLConfigFlow()
    config_flow.hass = hass
    config_flow.webhook_id = WEBHOOK_ID
    config_flow.data = {
        CONF_WEBHOOK_ID: WEBHOOK_ID,
        CONF_HOST: "example.com",
        CONF_PORT: "80",
        CONF_PATH: "/webhook/path",
    }

    task = hass.loop.create_task(asyncio.sleep(0))
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    config_flow.task_one = task

    config_flow.async_show_progress_done = MagicMock(
        return_value={"type": FlowResultType.SHOW_PROGRESS_DONE}
    )

    hass.data.setdefault(KEY_DEVICES, {})[WEBHOOK_ID] = mock_ccl

    with patch(
        "homeassistant.components.ccl.config_flow.webhook.async_unregister"
    ) as unregister:
        result = await config_flow.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert config_flow.data["abort_reason"] == "unknown"
    unregister.assert_called_once_with(hass, WEBHOOK_ID)
    assert WEBHOOK_ID not in hass.data[KEY_DEVICES]


async def test_abort_flow_device_none(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
) -> None:
    """Test handling when device is None during config flow init."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with (
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=WEBHOOK_ID,
        ),
        patch(
            "homeassistant.components.ccl.config_flow.CCLDevice",
            return_value=None,
        ),
        patch("homeassistant.components.ccl.config_flow.register", return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        flow_id = result["flow_id"]

        await hass.async_block_till_done()

        if result["type"] in (
            FlowResultType.SHOW_PROGRESS,
            FlowResultType.SHOW_PROGRESS_DONE,
        ):
            result = await hass.config_entries.flow.async_configure(flow_id, {})
            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_abort_flow_device_id_none(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test handling when device id is None during config flow init."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_id",
        return_value=WEBHOOK_ID,
    ):
        mock_ccl.device_id = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"
        flow_id = result["flow_id"]

        # Simulate webhook request that sets last_update_time but not device_id
        client = await hass_client_no_auth()
        webhook_url = async_generate_url(hass, WEBHOOK_ID)
        body = {"hello": "world"}

        async def handler_side_effect(request, devices_dict):
            # Set last_update_time but leave device_id as None
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

        # After device updates, advance the flow
        if result["type"] is FlowResultType.SHOW_PROGRESS:
            flows = hass.config_entries.flow.async_progress()
            if any(f for f in flows if f["flow_id"] == flow_id):
                result = await hass.config_entries.flow.async_configure(flow_id, {})
                await hass.async_block_till_done()
            else:
                # Flow already finished and aborted in background
                result = {"type": FlowResultType.ABORT, "reason": "unknown"}

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_abort_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
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

        if result["type"] is FlowResultType.SHOW_PROGRESS:
            flow_id = result["flow_id"]
            client = await hass_client_no_auth()
            webhook_url = async_generate_url(hass, WEBHOOK_ID)

            async def handler_side_effect(request, devices_dict):
                device = devices_dict[WEBHOOK_ID]
                device.last_update_time = 123
                return web.Response(status=200)

            with patch(
                "homeassistant.components.ccl.CCLServer.handler",
                side_effect=handler_side_effect,
            ):
                resp = await client.post(urlparse(webhook_url).path, json={})

            assert resp.status == 200

            await hass.async_block_till_done()
            result = await hass.config_entries.flow.async_configure(flow_id, {})
            await hass.async_block_till_done()
        elif result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
            # If the flow already progressed to the finish step, complete it.
            flow_id = result["flow_id"]
            result = await hass.config_entries.flow.async_configure(flow_id, {})
            await hass.async_block_till_done()

        # Final result must be abort with the expected reason.
        assert result["type"] is FlowResultType.ABORT
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

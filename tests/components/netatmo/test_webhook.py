"""The tests for Netatmo webhook events."""
from homeassistant.components.netatmo.webhook import async_handle_webhook
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.aiohttp import MockRequest


async def test_webhook_error_in_data(hass, config_entry):
    """Test that errors in webhook data are handled."""
    webhook_called = False

    async def handle_event(_):
        nonlocal webhook_called
        webhook_called = True

    response = b'""webhook_activation"}'
    request = MockRequest(content=response, mock_source="test")

    async_dispatcher_connect(
        hass,
        "signal-netatmo-webhook-None",
        handle_event,
    )

    await async_handle_webhook(hass, "webhook_id", request)
    await hass.async_block_till_done()

    assert not webhook_called

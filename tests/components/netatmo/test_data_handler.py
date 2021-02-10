"""The tests for Netatmo data handler."""
from time import time
from unittest.mock import patch

from homeassistant.components.netatmo import DOMAIN
from homeassistant.components.netatmo.data_handler import (
    CAMERA_DATA_CLASS_NAME,
    NetatmoDataHandler,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send


async def test_setup_component(hass, config_entry):
    """Test that setup entry works."""
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth:
        hass.data[DOMAIN] = {config_entry.entry_id: {"netatmo_auth": mock_auth()}}

    assert mock_auth.called
    mock_auth.post_request("foo", "bar")

    data_handler = NetatmoDataHandler(hass, config_entry)
    await data_handler.async_setup()
    await hass.async_block_till_done()

    assert data_handler._data_classes == {}

    webhook_data = {
        "user_id": "123",
        "user": {"id": "123", "email": "foo@bar.com"},
        "push_type": "webhook_activation",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-None",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    def fake_callback():
        pass

    await data_handler.register_data_class(
        CAMERA_DATA_CLASS_NAME, CAMERA_DATA_CLASS_NAME, fake_callback
    )
    await hass.async_block_till_done()

    assert "CameraData" in data_handler._data_classes
    assert mock_auth.post_request.called
    assert data_handler._data_classes["CameraData"]["subscriptions"] != []

    await data_handler.async_update(None)
    await hass.async_block_till_done()

    assert data_handler.webhook

    webhook_data = {
        "user_id": "123",
        "user": {"id": "123", "email": "foo@bar.com"},
        "push_type": "NACamera-connection",
    }
    async_dispatcher_send(
        hass,
        "signal-netatmo-webhook-None",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()

    data_handler._data_classes["CameraData"]["next_scan"] = time() - 1

    await data_handler.async_update(None)
    await hass.async_block_till_done()

    assert len(data_handler.listeners) == 1

    await data_handler.register_data_class(
        CAMERA_DATA_CLASS_NAME, CAMERA_DATA_CLASS_NAME, fake_callback
    )
    await hass.async_block_till_done()

    assert len(data_handler._data_classes["CameraData"]["subscriptions"]) == 2

    await data_handler.unregister_data_class(CAMERA_DATA_CLASS_NAME, fake_callback)
    await hass.async_block_till_done()

    assert len(data_handler._data_classes["CameraData"]["subscriptions"]) == 1

    def fake_callback_2():
        pass

    await data_handler.unregister_data_class(CAMERA_DATA_CLASS_NAME, fake_callback_2)
    await hass.async_block_till_done()

    assert len(data_handler._data_classes) == 1

    await data_handler.unregister_data_class(CAMERA_DATA_CLASS_NAME, fake_callback)
    await hass.async_block_till_done()

    assert len(data_handler._data_classes) == 0

    await data_handler.async_cleanup()
    await hass.async_block_till_done()

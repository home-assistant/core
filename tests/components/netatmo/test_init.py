"""The tests for Netatmo device triggers."""
from time import time
from unittest.mock import Mock, patch

import jwt

from homeassistant import config_entries
from homeassistant.components.netatmo import DOMAIN
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .common import fake_post_request

from tests.common import MockConfigEntry
from tests.components.cloud import mock_cloud


async def test_setup_component(hass):
    """Test setup and teardown of the netatmo component."""
    config_entry = MockConfigEntry(
        domain="netatmo",
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 1000,
                "scope": "read_station",
            },
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as mock_impl, patch(
        "homeassistant.components.webhook.async_generate_url"
    ) as mock_webhook:
        mock_auth.return_value.post_request.side_effect = fake_post_request
        assert await async_setup_component(hass, "netatmo", {})

    await hass.async_block_till_done()

    assert mock_auth.call_count == 1
    assert mock_impl.call_count == 1
    assert mock_webhook.call_count == 1

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)


async def test_setup_component_with_config(hass, config_entry):
    """Test setup of the netatmo component with dev account."""
    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as mock_impl, patch(
        "homeassistant.components.webhook.async_generate_url"
    ) as mock_webhook:
        mock_auth.return_value.post_request.side_effect = fake_post_request
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

    await hass.async_block_till_done()

    assert mock_auth.call_count == 1
    assert mock_impl.call_count == 1
    assert mock_webhook.call_count == 1

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert "camera" in hass.data
    assert "climate" in hass.data
    assert "light" in hass.data
    assert "sensor" in hass.data


async def test_setup_component_with_webhook(hass, entry):
    """Test setup and teardown of the netatmo component with webhook registration."""
    webhook_data = {
        "user_id": "123",
        "user": {"id": "123", "email": "foo@bar.com"},
        "push_type": "webhook_activation",
    }
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-None",
        {"type": None, "data": webhook_data},
    )
    await hass.async_block_till_done()
    assert hass.data["netatmo"][entry.entry_id]["netatmo_data_handler"].webhook is True

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)


async def test_setup_without_https(hass, config_entry):
    """Test if setup with cloud and without https."""
    hass.data["cloud"] = Mock()
    hass.data["cloud"].is_logged_in = True

    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ) as mock_webhook:
        mock_auth.return_value.post_request.side_effect = fake_post_request
        mock_webhook.return_value = "http://example.com"
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

    await hass.async_block_till_done()

    assert (
        hass.data["netatmo"][config_entry.entry_id]["netatmo_data_handler"].webhook
        is False
    )


async def test_setup_with_cloud(hass, config_entry):
    """Test if setup with cloud and without https."""
    await mock_cloud(hass)
    hass.data["cloud"].id_token = jwt.encode(
        {
            "email": "hello@home-assistant.io",
            "custom:sub-exp": "2018-01-03",
            "cognito:username": "abcdefghjkl",
        },
        "test",
    )
    await hass.async_block_till_done()
    assert hass.data["cloud"].is_logged_in is True

    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )
        assert hass.components.cloud.async_active_subscription() is True

    await hass.async_block_till_done()

    assert hass.components.cloud.async_active_subscription() is True

    assert (
        hass.data["netatmo"][config_entry.entry_id]["netatmo_data_handler"].webhook
        is False
    )

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)

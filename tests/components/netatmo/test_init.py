"""The tests for Netatmo component."""
from time import time
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.netatmo import DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from .common import FAKE_WEBHOOK_ACTIVATION, fake_post_request, simulate_webhook

from tests.common import MockConfigEntry
from tests.components.cloud import mock_cloud

# Fake webhook thermostat mode change to "Max"
FAKE_WEBHOOK = {
    "room_id": "2746182631",
    "home": {
        "id": "91763b24c43d3e344f424e8b",
        "name": "MYHOME",
        "country": "DE",
        "rooms": [
            {
                "id": "2746182631",
                "name": "Livingroom",
                "type": "livingroom",
                "therm_setpoint_mode": "max",
                "therm_setpoint_end_time": 1612749189,
            }
        ],
        "modules": [
            {"id": "12:34:56:00:01:ae", "name": "Livingroom", "type": "NATherm1"}
        ],
    },
    "mode": "max",
    "event_type": "set_point",
    "push_type": "display_change",
}


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

    mock_auth.assert_called_once()
    mock_impl.assert_called_once()
    mock_webhook.assert_called_once()

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED
    assert hass.config_entries.async_entries(DOMAIN)
    assert len(hass.states.async_all()) > 0

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_component_with_config(hass, config_entry):
    """Test setup of the netatmo component with dev account."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as mock_impl, patch(
        "homeassistant.components.webhook.async_generate_url"
    ) as mock_webhook, patch(
        "pyatmo.auth.NetatmoOAuth2.post_request"
    ) as fake_post_requests, patch(
        "homeassistant.components.netatmo.PLATFORMS", ["sensor"]
    ):
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

        await hass.async_block_till_done()

        fake_post_requests.assert_called()
        mock_impl.assert_called_once()
        mock_webhook.assert_called_once()

        assert config_entry.state == config_entries.ENTRY_STATE_LOADED
        assert hass.config_entries.async_entries(DOMAIN)
        assert len(hass.states.async_all()) > 0


async def test_setup_component_with_webhook(hass, entry):
    """Test setup and teardown of the netatmo component with webhook registration."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)

    assert len(hass.states.async_all()) > 0

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)

    # Assert webhook is established successfully
    climate_entity_livingroom = "climate.netatmo_livingroom"
    assert hass.states.get(climate_entity_livingroom).state == "auto"
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK)
    assert hass.states.get(climate_entity_livingroom).state == "heat"

    for config_entry in hass.config_entries.async_entries("netatmo"):
        await hass.config_entries.async_remove(config_entry.entry_id)

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_setup_without_https(hass, config_entry):
    """Test if set up with cloud link and without https."""
    hass.config.components.add("cloud")
    with patch(
        "homeassistant.helpers.network.get_url",
        return_value="https://example.nabu.casa",
    ), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ) as mock_webhook:
        mock_auth.return_value.post_request.side_effect = fake_post_request
        mock_webhook.return_value = "https://example.com"
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )

    await hass.async_block_till_done()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK_ACTIVATION)

    # Assert webhook is established successfully
    climate_entity_livingroom = "climate.netatmo_livingroom"
    assert hass.states.get(climate_entity_livingroom).state == "auto"
    await simulate_webhook(hass, webhook_id, FAKE_WEBHOOK)
    await hass.async_block_till_done()
    assert hass.states.get(climate_entity_livingroom).state == "heat"


async def test_setup_with_cloud(hass, config_entry):
    """Test if set up with active cloud subscription."""
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloud.async_is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ) as fake_create_cloudhook, patch(
        "homeassistant.components.cloud.async_delete_cloudhook"
    ) as fake_delete_cloudhook, patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.components.netatmo.PLATFORMS", []
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        assert await async_setup_component(
            hass, "netatmo", {"netatmo": {"client_id": "123", "client_secret": "abc"}}
        )
        assert hass.components.cloud.async_active_subscription() is True
        fake_create_cloudhook.assert_called_once()

        assert (
            hass.config_entries.async_entries("netatmo")[0].data["cloudhook_url"]
            == "https://hooks.nabu.casa/ABCD"
        )

        await hass.async_block_till_done()
        assert hass.config_entries.async_entries(DOMAIN)

        for config_entry in hass.config_entries.async_entries("netatmo"):
            await hass.config_entries.async_remove(config_entry.entry_id)
            fake_delete_cloudhook.assert_called_once()

        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)

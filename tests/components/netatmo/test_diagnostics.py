"""Test the Netatmo diagnostics."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.setup import async_setup_component

from .common import fake_post_request

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client, config_entry):
    """Test config entry diagnostics."""
    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth",
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.netatmo.webhook_generate_url"
    ):
        mock_auth.return_value.async_post_request.side_effect = fake_post_request
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await async_setup_component(hass, "netatmo", {})

    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    # ignore for tests
    result["info"]["data"]["token"].pop("expires_at")
    result["info"].pop("entry_id")

    assert result["info"] == {
        "data": {
            "auth_implementation": "cloud",
            "token": {
                "access_token": REDACTED,
                "expires_in": 60,
                "refresh_token": REDACTED,
                "scope": [
                    "read_station",
                    "read_camera",
                    "access_camera",
                    "write_camera",
                    "read_presence",
                    "access_presence",
                    "write_presence",
                    "read_homecoach",
                    "read_smokedetector",
                    "read_thermostat",
                    "write_thermostat",
                ],
                "type": "Bearer",
            },
            "webhook_id": REDACTED,
        },
        "disabled_by": None,
        "domain": "netatmo",
        "options": {
            "weather_areas": {
                "Home avg": {
                    "area_name": "Home avg",
                    "lat_ne": REDACTED,
                    "lat_sw": REDACTED,
                    "lon_ne": REDACTED,
                    "lon_sw": REDACTED,
                    "mode": "avg",
                    "show_on_map": False,
                },
                "Home max": {
                    "area_name": "Home max",
                    "lat_ne": REDACTED,
                    "lat_sw": REDACTED,
                    "lon_ne": REDACTED,
                    "lon_sw": REDACTED,
                    "mode": "max",
                    "show_on_map": True,
                },
            }
        },
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "title": "Mock Title",
        "unique_id": "netatmo",
        "version": 1,
        "webhook_registered": False,
    }

    for home in result["data"]["AsyncClimateTopology"]["homes"]:
        assert home["coordinates"] == REDACTED

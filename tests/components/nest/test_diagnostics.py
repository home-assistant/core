"""Test nest diagnostics."""

from unittest.mock import patch

from google_nest_sdm.exceptions import SubscriberException
import pytest

from homeassistant.config_entries import ConfigEntryState

from .common import TEST_CONFIG_LEGACY

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass, hass_client, create_device, setup_platform, config_entry
):
    """Test config entry diagnostics."""
    create_device.create(
        raw_data={
            "name": "enterprises/project-id/devices/device-id",
            "type": "sdm.devices.types.THERMOSTAT",
            "assignee": "enterprises/project-id/structures/structure-id/rooms/room-id",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "My Sensor",
                },
                "sdm.devices.traits.Temperature": {
                    "ambientTemperatureCelsius": 25.1,
                },
                "sdm.devices.traits.Humidity": {
                    "ambientHumidityPercent": 35.0,
                },
            },
            "parentRelations": [
                {
                    "parent": "enterprises/project-id/structures/structure-id/rooms/room-id",
                    "displayName": "Lobby",
                }
            ],
        }
    )
    await setup_platform()
    assert config_entry.state is ConfigEntryState.LOADED

    # Test that only non identifiable device information is returned
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "devices": [
            {
                "data": {
                    "assignee": "**REDACTED**",
                    "name": "**REDACTED**",
                    "parentRelations": [
                        {"displayName": "**REDACTED**", "parent": "**REDACTED**"}
                    ],
                    "traits": {
                        "sdm.devices.traits.Info": {"customName": "**REDACTED**"},
                        "sdm.devices.traits.Humidity": {"ambientHumidityPercent": 35.0},
                        "sdm.devices.traits.Temperature": {
                            "ambientTemperatureCelsius": 25.1
                        },
                    },
                    "type": "sdm.devices.types.THERMOSTAT",
                }
            }
        ],
    }


async def test_setup_susbcriber_failure(
    hass, hass_client, config_entry, setup_base_platform
):
    """Test configuration error."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=SubscriberException(),
    ):
        await setup_base_platform()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "error": "No subscriber configured"
    }


@pytest.mark.parametrize("nest_test_config", [TEST_CONFIG_LEGACY])
async def test_legacy_config_entry_diagnostics(
    hass, hass_client, config_entry, setup_base_platform
):
    """Test config entry diagnostics for legacy integration doesn't fail."""

    with patch("homeassistant.components.nest.legacy.Nest"):
        await setup_base_platform()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {}

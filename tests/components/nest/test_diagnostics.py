"""Test nest diagnostics."""

from unittest.mock import patch

from google_nest_sdm.device import Device
from google_nest_sdm.exceptions import SubscriberException

from homeassistant.components.nest import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from .common import CONFIG, async_setup_sdm_platform, create_config_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry

THERMOSTAT_TYPE = "sdm.devices.types.THERMOSTAT"


async def test_entry_diagnostics(hass, hass_client):
    """Test config entry diagnostics."""
    devices = {
        "some-device-id": Device.MakeDevice(
            {
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
            },
            auth=None,
        )
    }
    assert await async_setup_sdm_platform(hass, platform=None, devices=devices)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    config_entry = entries[0]
    assert config_entry.state is ConfigEntryState.LOADED

    # Test that only non identifiable device information is returned
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "devices": [
            {
                "traits": {
                    "sdm.devices.traits.Humidity": {"ambientHumidityPercent": 35.0},
                    "sdm.devices.traits.Temperature": {
                        "ambientTemperatureCelsius": 25.1
                    },
                },
                "type": "sdm.devices.types.THERMOSTAT",
            }
        ],
    }


async def test_setup_susbcriber_failure(hass, hass_client):
    """Test configuration error."""
    config_entry = create_config_entry()
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ), patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=SubscriberException(),
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "error": "No subscriber configured"
    }

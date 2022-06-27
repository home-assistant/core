"""Test diagnostics."""

from typing import Any
from unittest.mock import ANY

from homeassistant import core, setup
from homeassistant.components import google_assistant as ga, switch
from homeassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass: core.HomeAssistant, hass_client: Any):
    """Test diagnostics v1."""

    await setup.async_setup_component(
        hass, switch.DOMAIN, {"switch": [{"platform": "demo"}]}
    )

    await async_setup_component(
        hass,
        ga.DOMAIN,
        {"google_assistant": DUMMY_CONFIG},
    )

    config_entry = hass.config_entries.async_entries("google_assistant")[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == {
        "config_entry": {
            "data": {"project_id": "1234"},
            "disabled_by": None,
            "domain": "google_assistant",
            "entry_id": ANY,
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "import",
            "title": "1234",
            "unique_id": "1234",
            "version": 1,
        },
        "sync": {
            "agentUserId": "**REDACTED**",
            "devices": [
                {
                    "attributes": {"commandOnlyOnOff": True},
                    "id": "switch.decorative_lights",
                    "otherDeviceIds": [{"deviceId": "switch.decorative_lights"}],
                    "name": {"name": "Decorative Lights"},
                    "traits": ["action.devices.traits.OnOff"],
                    "type": "action.devices.types.SWITCH",
                    "willReportState": False,
                    "customData": {
                        "baseUrl": "**REDACTED**",
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": "**REDACTED**",
                        "uuid": "**REDACTED**",
                        "webhookId": None,
                    },
                },
                {
                    "attributes": {},
                    "id": "switch.ac",
                    "otherDeviceIds": [{"deviceId": "switch.ac"}],
                    "name": {"name": "AC"},
                    "traits": ["action.devices.traits.OnOff"],
                    "type": "action.devices.types.OUTLET",
                    "willReportState": False,
                    "customData": {
                        "baseUrl": "**REDACTED**",
                        "httpPort": 8123,
                        "httpSSL": False,
                        "proxyDeviceId": "**REDACTED**",
                        "uuid": "**REDACTED**",
                        "webhookId": None,
                    },
                },
            ],
        },
        "yaml_config": {
            "expose_by_default": True,
            "exposed_domains": [
                "alarm_control_panel",
                "binary_sensor",
                "climate",
                "cover",
                "fan",
                "group",
                "humidifier",
                "input_boolean",
                "input_select",
                "light",
                "lock",
                "media_player",
                "scene",
                "script",
                "select",
                "sensor",
                "switch",
                "vacuum",
            ],
            "project_id": "1234",
            "report_state": False,
            "service_account": "**REDACTED**",
        },
    }

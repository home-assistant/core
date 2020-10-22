"""Test websocket API."""
from pathlib import Path

import pytest

from homeassistant.components import automation
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_bp(hass):
    """Fixture to set up the blueprint component."""
    assert await async_setup_component(hass, "blueprint", {})

    # Trigger registration of automation blueprints
    automation.async_get_blueprints(hass)


async def test_list_blueprints(hass, hass_ws_client):
    """Test listing blueprints."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "blueprint/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    blueprints = msg["result"]
    assert blueprints.get("automation") == {
        "test_event_service.yaml": {
            "metadata": {
                "domain": "automation",
                "input": {"service_to_call": None, "trigger_event": None},
                "name": "Call service based on event",
            },
        },
        "in_folder/in_folder_blueprint.yaml": {
            "metadata": {
                "domain": "automation",
                "input": {"action": None, "trigger": None},
                "name": "In Folder Blueprint",
            }
        },
    }


async def test_import_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test listing blueprints."""
    raw_data = Path(
        hass.config.path("blueprints/automation/test_event_service.yaml")
    ).read_text()

    aioclient_mock.get(
        "https://raw.githubusercontent.com/balloob/home-assistant-config/main/blueprints/automation/motion_light.yaml",
        text=raw_data,
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "blueprint/import",
            "url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        "suggested_filename": "balloob-motion_light",
        "url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
        "raw_data": raw_data,
        "blueprint": {
            "metadata": {
                "domain": "automation",
                "input": {"service_to_call": None, "trigger_event": None},
                "name": "Call service based on event",
            },
        },
    }

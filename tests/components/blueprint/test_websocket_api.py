"""Test websocket API."""
from pathlib import Path

import pytest

from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch


@pytest.fixture(autouse=True)
async def setup_bp(hass):
    """Fixture to set up the blueprint component."""
    assert await async_setup_component(hass, "blueprint", {})

    # Trigger registration of automation blueprints
    await async_setup_component(hass, "automation", {})


async def test_list_blueprints(hass, hass_ws_client):
    """Test listing blueprints."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "blueprint/list", "domain": "automation"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    blueprints = msg["result"]
    assert blueprints == {
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


async def test_list_blueprints_non_existing_domain(hass, hass_ws_client):
    """Test listing blueprints."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "blueprint/list", "domain": "not_existsing"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    blueprints = msg["result"]
    assert blueprints == {}


async def test_import_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test importing blueprints."""
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
        "suggested_filename": "balloob/motion_light",
        "raw_data": raw_data,
        "blueprint": {
            "metadata": {
                "domain": "automation",
                "input": {"service_to_call": None, "trigger_event": None},
                "name": "Call service based on event",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
            },
        },
        "validation_errors": None,
    }


async def test_save_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test saving blueprints."""
    raw_data = Path(
        hass.config.path("blueprints/automation/test_event_service.yaml")
    ).read_text()

    with patch("pathlib.Path.write_text") as write_mock:
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 6,
                "type": "blueprint/save",
                "path": "test_save",
                "yaml": raw_data,
                "domain": "automation",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
            }
        )

        msg = await client.receive_json()

        assert msg["id"] == 6
        assert msg["success"]
        assert write_mock.mock_calls
        assert write_mock.call_args[0] == (
            "blueprint:\n  name: Call service based on event\n  domain: automation\n  input:\n    trigger_event:\n    service_to_call:\n  source_url: https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml\ntrigger:\n  platform: event\n  event_type: !input 'trigger_event'\naction:\n  service: !input 'service_to_call'\n  entity_id: light.kitchen\n",
        )


async def test_save_existing_file(hass, aioclient_mock, hass_ws_client):
    """Test saving blueprints."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 7,
            "type": "blueprint/save",
            "path": "test_event_service",
            "yaml": 'blueprint: {name: "name", domain: "automation"}',
            "domain": "automation",
            "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 7
    assert not msg["success"]
    assert msg["error"] == {"code": "already_exists", "message": "File already exists"}


async def test_save_file_error(hass, aioclient_mock, hass_ws_client):
    """Test saving blueprints with OS error."""
    with patch("pathlib.Path.write_text", side_effect=OSError):
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 8,
                "type": "blueprint/save",
                "path": "test_save",
                "yaml": "raw_data",
                "domain": "automation",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
            }
        )

        msg = await client.receive_json()

        assert msg["id"] == 8
        assert not msg["success"]


async def test_save_invalid_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test saving invalid blueprints."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 8,
            "type": "blueprint/save",
            "path": "test_wrong",
            "yaml": "wrong_blueprint",
            "domain": "automation",
            "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 8
    assert not msg["success"]
    assert msg["error"] == {
        "code": "invalid_format",
        "message": "Invalid blueprint: expected a dictionary. Got 'wrong_blueprint'",
    }


async def test_delete_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test deleting blueprints."""

    with patch("pathlib.Path.unlink", return_value=Mock()) as unlink_mock:
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 9,
                "type": "blueprint/delete",
                "path": "test_delete",
                "domain": "automation",
            }
        )

        msg = await client.receive_json()

        assert unlink_mock.mock_calls
        assert msg["id"] == 9
        assert msg["success"]


async def test_delete_non_exist_file_blueprint(hass, aioclient_mock, hass_ws_client):
    """Test deleting non existing blueprints."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 9,
            "type": "blueprint/delete",
            "path": "none_existing",
            "domain": "automation",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 9
    assert not msg["success"]

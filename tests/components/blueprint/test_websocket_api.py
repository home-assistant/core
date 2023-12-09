"""Test websocket API."""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import parse_yaml

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
def automation_config():
    """Automation config."""
    return {}


@pytest.fixture
def script_config():
    """Script config."""
    return {}


@pytest.fixture(autouse=True)
async def setup_bp(hass, automation_config, script_config):
    """Fixture to set up the blueprint component."""
    assert await async_setup_component(hass, "blueprint", {})

    # Trigger registration of automation and script blueprints
    await async_setup_component(hass, "automation", automation_config)
    await async_setup_component(hass, "script", script_config)


async def test_list_blueprints(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
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
                "input": {
                    "service_to_call": None,
                    "trigger_event": {"selector": {"text": {}}},
                    "a_number": {"selector": {"number": {"mode": "box", "step": 1.0}}},
                },
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


async def test_list_blueprints_non_existing_domain(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing blueprints."""
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "blueprint/list", "domain": "not_existing"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    blueprints = msg["result"]
    assert blueprints == {}


async def test_import_blueprint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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
                "input": {
                    "service_to_call": None,
                    "trigger_event": {"selector": {"text": {}}},
                    "a_number": {"selector": {"number": {"mode": "box", "step": 1.0}}},
                },
                "name": "Call service based on event",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
            },
        },
        "validation_errors": None,
        "exists": False,
    }


async def test_import_blueprint_update(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
    setup_bp,
) -> None:
    """Test importing blueprints."""
    raw_data = Path(
        hass.config.path("blueprints/automation/in_folder/in_folder_blueprint.yaml")
    ).read_text()

    aioclient_mock.get(
        "https://raw.githubusercontent.com/in_folder/home-assistant-config/main/blueprints/automation/in_folder_blueprint.yaml",
        text=raw_data,
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "blueprint/import",
            "url": "https://github.com/in_folder/home-assistant-config/blob/main/blueprints/automation/in_folder_blueprint.yaml",
        }
    )

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        "suggested_filename": "in_folder/in_folder_blueprint",
        "raw_data": raw_data,
        "blueprint": {
            "metadata": {
                "domain": "automation",
                "input": {"action": None, "trigger": None},
                "name": "In Folder Blueprint",
                "source_url": "https://github.com/in_folder/home-assistant-config/blob/main/blueprints/automation/in_folder_blueprint.yaml",
            }
        },
        "validation_errors": None,
        "exists": True,
    }


async def test_save_blueprint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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
        # There are subtle differences in the dumper quoting
        # behavior when quoting is not required as both produce
        # valid yaml
        output_yaml = write_mock.call_args[0][0]
        assert output_yaml in (
            # pure python dumper will quote the value after !input
            "blueprint:\n  name: Call service based on event\n  domain: automation\n "
            " input:\n    trigger_event:\n      selector:\n        text: {}\n   "
            " service_to_call:\n    a_number:\n      selector:\n        number:\n      "
            "    mode: box\n          step: 1.0\n  source_url:"
            " https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml\ntrigger:\n"
            "  platform: event\n  event_type: !input 'trigger_event'\naction:\n "
            " service: !input 'service_to_call'\n  entity_id: light.kitchen\n"
            # c dumper will not quote the value after !input
            "blueprint:\n  name: Call service based on event\n  domain: automation\n "
            " input:\n    trigger_event:\n      selector:\n        text: {}\n   "
            " service_to_call:\n    a_number:\n      selector:\n        number:\n      "
            "    mode: box\n          step: 1.0\n  source_url:"
            " https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml\ntrigger:\n"
            "  platform: event\n  event_type: !input trigger_event\naction:\n  service:"
            " !input service_to_call\n  entity_id: light.kitchen\n"
        )
        # Make sure ita parsable and does not raise
        assert len(parse_yaml(output_yaml)) > 1


async def test_save_existing_file(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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


async def test_save_existing_file_override(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test saving blueprints."""

    client = await hass_ws_client(hass)
    with patch("pathlib.Path.write_text") as write_mock:
        await client.send_json(
            {
                "id": 7,
                "type": "blueprint/save",
                "path": "test_event_service",
                "yaml": 'blueprint: {name: "name", domain: "automation"}',
                "domain": "automation",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/test_event_service.yaml",
                "allow_override": True,
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 7
    assert msg["success"]
    assert msg["result"] == {"overrides_existing": True}
    assert yaml.safe_load(write_mock.mock_calls[0][1][0]) == {
        "blueprint": {
            "name": "name",
            "domain": "automation",
            "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/test_event_service.yaml",
            "input": {},
        }
    }


async def test_save_file_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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


async def test_save_invalid_blueprint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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


async def test_delete_blueprint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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


async def test_delete_non_exist_file_blueprint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
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


@pytest.mark.parametrize(
    "automation_config",
    (
        {
            "automation": {
                "use_blueprint": {
                    "path": "test_event_service.yaml",
                    "input": {
                        "trigger_event": "blueprint_event",
                        "service_to_call": "test.automation",
                        "a_number": 5,
                    },
                }
            }
        },
    ),
)
async def test_delete_blueprint_in_use_by_automation(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test deleting a blueprint which is in use."""

    with patch("pathlib.Path.unlink", return_value=Mock()) as unlink_mock:
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 9,
                "type": "blueprint/delete",
                "path": "test_event_service.yaml",
                "domain": "automation",
            }
        )

        msg = await client.receive_json()

        assert not unlink_mock.mock_calls
        assert msg["id"] == 9
        assert not msg["success"]
        assert msg["error"] == {
            "code": "home_assistant_error",
            "message": "Blueprint in use",
        }


@pytest.mark.parametrize(
    "script_config",
    (
        {
            "script": {
                "test_script": {
                    "use_blueprint": {
                        "path": "test_service.yaml",
                        "input": {
                            "service_to_call": "test.automation",
                        },
                    }
                }
            }
        },
    ),
)
async def test_delete_blueprint_in_use_by_script(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test deleting a blueprint which is in use."""

    with patch("pathlib.Path.unlink", return_value=Mock()) as unlink_mock:
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 9,
                "type": "blueprint/delete",
                "path": "test_service.yaml",
                "domain": "script",
            }
        )

        msg = await client.receive_json()

        assert not unlink_mock.mock_calls
        assert msg["id"] == 9
        assert not msg["success"]
        assert msg["error"] == {
            "code": "home_assistant_error",
            "message": "Blueprint in use",
        }

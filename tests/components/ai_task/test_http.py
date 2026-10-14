"""Test the HTTP API for AI Task integration."""

import pytest

from homeassistant.core import HomeAssistant

from tests.typing import WebSocketGenerator


async def test_ws_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_components: None,
) -> None:
    """Test preferences via the WebSocket API."""
    client = await hass_ws_client(hass)

    # Get initial preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": None,
        "gen_image_entity_id": None,
    }

    # Set preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": "ai_task.summary_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_1",
        "gen_image_entity_id": None,
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_1",
        "gen_image_entity_id": None,
    }

    # Update an existing preference
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": "ai_task.summary_2",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_2",
        "gen_image_entity_id": None,
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_2",
        "gen_image_entity_id": None,
    }

    # No preferences set will preserve existing preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_2",
        "gen_image_entity_id": None,
    }

    # Get updated preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_2",
        "gen_image_entity_id": None,
    }

    # Set gen_image_entity_id preference
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_image_entity_id": "ai_task.image_gen_1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_2",
        "gen_image_entity_id": "ai_task.image_gen_1",
    }

    # Update both preferences
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "gen_data_entity_id": "ai_task.summary_3",
            "gen_image_entity_id": "ai_task.image_gen_2",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_3",
        "gen_image_entity_id": "ai_task.image_gen_2",
    }

    # Get final preferences
    await client.send_json_auto_id({"type": "ai_task/preferences/get"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "allow_automatic_evaluation": False,
        "evaluate_entity_id": None,
        "gen_data_entity_id": "ai_task.summary_3",
        "gen_image_entity_id": "ai_task.image_gen_2",
    }


@pytest.mark.usefixtures("init_components")
async def test_ws_automatic_evaluation_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Automatic use is an explicit opt-in independent of the default entity."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "ai_task/preferences/set",
            "evaluate_entity_id": "ai_task.decision",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["allow_automatic_evaluation"] is False

    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "allow_automatic_evaluation": True}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["allow_automatic_evaluation"] is True
    assert msg["result"]["evaluate_entity_id"] == "ai_task.decision"

    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "gen_data_entity_id": "ai_task.data"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["allow_automatic_evaluation"] is True

    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "allow_automatic_evaluation": False}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["allow_automatic_evaluation"] is False
    assert msg["result"]["evaluate_entity_id"] == "ai_task.decision"


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize("value", [None, "true", 1, {}])
async def test_ws_automatic_evaluation_invalid(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    value: object,
) -> None:
    """Only booleans can opt in to automatic use."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "allow_automatic_evaluation": value}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("init_components")
async def test_ws_automatic_evaluation_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Only administrators can allow automatic use."""
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "allow_automatic_evaluation": True}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"

"""Test sandbox entity proxy architecture."""

from unittest.mock import patch

import pytest

from homeassistant.components.sandbox import (
    SandboxData,
    SandboxEntryData,
    SandboxInstance,
)
from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.components.sandbox.entity import (
    SandboxEntityManager,
    SandboxLightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
async def sandbox_setup(hass: HomeAssistant) -> tuple[str, MockConfigEntry]:
    """Set up the sandbox integration with a mock config entry."""
    assert await async_setup_component(hass, "sandbox", {})

    sandbox_id = "test_sandbox_123"
    entry = MockConfigEntry(
        domain="sandbox",
        entry_id=sandbox_id,
        data={
            "entries": [
                {
                    "entry_id": "hue_entry_1",
                    "domain": "hue",
                    "title": "Hue Bridge",
                    "data": {"host": "192.168.1.100"},
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sandbox._spawn_sandbox",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    return sandbox_id, entry


async def test_entity_manager_created(
    hass: HomeAssistant, sandbox_setup: tuple[str, MockConfigEntry]
) -> None:
    """Test that entity manager is created during setup."""
    sandbox_id, _ = sandbox_setup
    sandbox_data: SandboxData = hass.data[DATA_SANDBOX]
    assert sandbox_id in sandbox_data.entity_managers
    manager = sandbox_data.entity_managers[sandbox_id]
    assert isinstance(manager, SandboxEntityManager)


async def test_register_entity_creates_proxy(
    hass: HomeAssistant, sandbox_setup: tuple[str, MockConfigEntry]
) -> None:
    """Test that registering an entity creates a proxy and tracks it."""
    sandbox_id, entry = sandbox_setup
    sandbox_data: SandboxData = hass.data[DATA_SANDBOX]
    manager = sandbox_data.entity_managers[sandbox_id]

    from homeassistant.components.sandbox.entity import SandboxEntityDescription

    description = SandboxEntityDescription(
        domain="light",
        platform="hue",
        unique_id=f"{sandbox_id}_light_living_room",
        sandbox_id=sandbox_id,
        sandbox_entry_id="hue_entry_1",
        original_name="Living Room",
        supported_features=0,
        capabilities={"supported_color_modes": ["brightness"]},
    )

    # Forward the light platform setup
    await hass.config_entries.async_forward_entry_setups(entry, ["light"])

    # Verify platform callback is registered
    assert "light" in manager._platform_add_callbacks

    # Create and add the entity
    entity = manager.add_entity(description)
    assert isinstance(entity, SandboxLightEntity)

    add_entities = manager._platform_add_callbacks["light"]
    add_entities([entity])

    await hass.async_block_till_done()

    # Entity should now have an entity_id and be tracked
    assert entity.entity_id is not None
    assert entity.entity_id.startswith("light.")
    assert manager.get_entity(entity.entity_id) is entity


async def test_proxy_entity_state_update(
    hass: HomeAssistant, sandbox_setup: tuple[str, MockConfigEntry]
) -> None:
    """Test that state updates from sandbox reach the proxy entity."""
    sandbox_id, entry = sandbox_setup
    sandbox_data: SandboxData = hass.data[DATA_SANDBOX]
    manager = sandbox_data.entity_managers[sandbox_id]

    from homeassistant.components.sandbox.entity import SandboxEntityDescription

    description = SandboxEntityDescription(
        domain="light",
        platform="hue",
        unique_id=f"{sandbox_id}_light_kitchen",
        sandbox_id=sandbox_id,
        sandbox_entry_id="hue_entry_1",
        original_name="Kitchen",
        supported_features=0,
        capabilities={"supported_color_modes": ["brightness"]},
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["light"])

    entity = manager.add_entity(description)
    add_entities = manager._platform_add_callbacks["light"]
    add_entities([entity])
    await hass.async_block_till_done()

    # Update state from sandbox
    entity.sandbox_update_state("on", {"brightness": 200, "color_mode": "brightness"})

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 200


async def test_proxy_entity_forwards_method(
    hass: HomeAssistant, sandbox_setup: tuple[str, MockConfigEntry]
) -> None:
    """Test that proxy entity forwards method calls to sandbox."""
    sandbox_id, entry = sandbox_setup
    sandbox_data: SandboxData = hass.data[DATA_SANDBOX]
    manager = sandbox_data.entity_managers[sandbox_id]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    from homeassistant.components.sandbox.entity import SandboxEntityDescription

    description = SandboxEntityDescription(
        domain="light",
        platform="hue",
        unique_id=f"{sandbox_id}_light_bedroom",
        sandbox_id=sandbox_id,
        sandbox_entry_id="hue_entry_1",
        original_name="Bedroom",
        supported_features=0,
        capabilities={"supported_color_modes": ["brightness"]},
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["light"])

    entity = manager.add_entity(description)
    add_entities = manager._platform_add_callbacks["light"]
    add_entities([entity])
    await hass.async_block_till_done()

    # Set up a mock send_command
    sent_commands: list[dict] = []

    def mock_send_command(command: dict) -> None:
        sent_commands.append(command)
        # Simulate immediate success response
        call_id = command["call_id"]
        manager.resolve_call(call_id, None, None)

    sandbox_info.send_command = mock_send_command

    # Call turn_on on the proxy
    await entity.async_turn_on(brightness=128)

    assert len(sent_commands) == 1
    cmd = sent_commands[0]
    assert cmd["type"] == "call_method"
    assert cmd["entity_id"] == entity.entity_id
    assert cmd["method"] == "async_turn_on"
    assert cmd["kwargs"] == {"brightness": 128}

"""End-to-end test for sandbox integration with input_boolean."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from homeassistant.components.sandbox.const import DATA_SANDBOX, DOMAIN as SANDBOX_DOMAIN
from homeassistant.components.sandbox import async_setup as sandbox_async_setup

from tests.common import MockConfigEntry, async_test_home_assistant


def test_sandbox_setup_creates_token_and_instance() -> None:
    """Test that sandbox setup creates auth tokens and sandbox instances."""

    async def run() -> None:
        async with async_test_home_assistant() as hass:
            await sandbox_async_setup(hass, {})

            entry = MockConfigEntry(
                domain=SANDBOX_DOMAIN,
                data={
                    "entries": [
                        {
                            "entry_id": "test_input_bool_1",
                            "domain": "input_boolean",
                            "title": "Test Switch",
                            "data": {
                                "items": [
                                    {
                                        "id": "my_switch",
                                        "name": "My Switch",
                                        "initial": False,
                                    }
                                ]
                            },
                        }
                    ]
                },
            )
            entry.add_to_hass(hass)

            with patch(
                "homeassistant.components.sandbox._spawn_sandbox",
                return_value=None,
            ):
                result = await hass.config_entries.async_setup(entry.entry_id)
                assert result is True

            sandbox_data = hass.data[DATA_SANDBOX]
            instance = sandbox_data.sandboxes[entry.entry_id]
            assert instance is not None
            assert instance.access_token is not None
            assert instance.refresh_token is not None
            assert len(instance.entries) == 1
            assert instance.entries[0]["domain"] == "input_boolean"
            assert instance.refresh_token.id in sandbox_data.token_to_sandbox

    asyncio.run(run())


def test_sandbox_state_update() -> None:
    """Test that state can be set (simulating sandbox/update_state)."""

    async def run() -> None:
        async with async_test_home_assistant() as hass:
            hass.states.async_set(
                "input_boolean.test_switch",
                "off",
                {"friendly_name": "Test"},
            )
            state = hass.states.get("input_boolean.test_switch")
            assert state is not None
            assert state.state == "off"

            hass.states.async_set(
                "input_boolean.test_switch",
                "on",
                {"friendly_name": "Test", "editable": True},
            )
            state = hass.states.get("input_boolean.test_switch")
            assert state is not None
            assert state.state == "on"
            assert state.attributes["editable"] is True

    asyncio.run(run())


def test_sandbox_unload_cleans_up() -> None:
    """Test that unloading a sandbox config entry cleans up resources."""

    async def run() -> None:
        async with async_test_home_assistant() as hass:
            await sandbox_async_setup(hass, {})

            entry = MockConfigEntry(
                domain=SANDBOX_DOMAIN,
                data={
                    "entries": [
                        {
                            "entry_id": "test_1",
                            "domain": "input_boolean",
                            "title": "Test",
                            "data": {"items": [{"id": "x", "name": "X"}]},
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

            sandbox_data = hass.data[DATA_SANDBOX]
            assert entry.entry_id in sandbox_data.sandboxes
            token_id = sandbox_data.sandboxes[entry.entry_id].refresh_token.id

            await hass.config_entries.async_unload(entry.entry_id)

            assert entry.entry_id not in sandbox_data.sandboxes
            assert token_id not in sandbox_data.token_to_sandbox

    asyncio.run(run())

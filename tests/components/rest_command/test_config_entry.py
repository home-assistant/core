"""Tests for REST commands set up from a config entry."""

from typing import Any
from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.rest_command.const import DOMAIN, SUBENTRY_TYPE_COMMAND
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_URL


def _entry(**commands: dict[str, Any]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="RESTful Command",
        subentries_data=[
            ConfigSubentryData(
                data=command,
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title=action,
                unique_id=action,
            )
            for action, command in commands.items()
        ],
    )


async def test_call_command_from_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a command from the UI renders its templates with the action data."""
    entry = _entry(
        open_door={
            "url": TEST_URL + "{{ door }}",
            "method": "post",
            "payload": '{"door": "{{ door }}"}',
            "headers": {"X-Door": "{{ door }}"},
            "content_type": "application/json",
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    aioclient_mock.post(
        TEST_URL + "front",
        content=b'{"ok": true}',
        headers={"Content-Type": "application/json"},
    )
    response = await hass.services.async_call(
        DOMAIN,
        "open_door",
        {"door": "front"},
        blocking=True,
        return_response=True,
    )

    assert response["content"] == {"ok": True}
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == b'{"door": "front"}'
    assert aioclient_mock.mock_calls[0][3]["X-Door"] == "front"


async def test_unload_removes_actions(hass: HomeAssistant) -> None:
    """Test unloading the entry removes its actions and keeps reload."""
    entry = _entry(from_ui={"url": TEST_URL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "from_ui")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(DOMAIN, "from_ui")
    assert hass.services.has_service(DOMAIN, "reload")


async def test_invalid_stored_command(hass: HomeAssistant) -> None:
    """Test a stored command that no longer validates does not block the others."""
    entry = _entry(broken={"url": "{{ door"}, working={"url": TEST_URL})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "broken")
    assert hass.services.has_service(DOMAIN, "working")


async def test_reload_keeps_ui_commands(hass: HomeAssistant) -> None:
    """Test reloading YAML leaves the commands from the UI alone."""
    entry = _entry(from_ui={"url": TEST_URL + "ui"})
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"from_yaml": {"url": TEST_URL}, "from_ui": {"url": TEST_URL}}},
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={DOMAIN: {"from_ui": {"url": TEST_URL}}},
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    assert not hass.services.has_service(DOMAIN, "from_yaml")
    assert hass.services.has_service(DOMAIN, "from_ui")

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "from_ui")

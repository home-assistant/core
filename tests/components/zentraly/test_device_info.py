"""Exercise real library metadata reads through Home Assistant."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from zentraly.client import CommandResult

from homeassistant.components.zentraly.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID, ENTITY_ID


async def test_optional_version_timeout_preserves_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    mock_climate_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A hardware timeout preserves availability even with polling disabled."""
    hass.config_entries.async_update_entry(mock_config_entry, pref_disable_polling=True)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_ID)},
        sw_version="1.0",
        hw_version="2.0",
    )
    release_metadata = asyncio.Event()
    responses: list[CommandResult | None] = [
        (
            7,
            {
                "cmd": "readAttr",
                "rid": 7,
                "status": 200,
                "attrs": [{"id": 2, "val": "1.1"}],
            },
        ),
        None,
    ]

    async def read_version(
        command_builder: Callable[[int], dict[str, Any]],
    ) -> CommandResult | None:
        await release_metadata.wait()
        return responses.pop(0)

    mock_api.async_execute_command.side_effect = read_version
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_ID, "heat")
    mock_climate_api.async_get_current_temperature.assert_awaited_once()

    release_metadata.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.is_state(ENTITY_ID, "heat")
    assert mock_config_entry.runtime_data.device.available
    updated = device_registry.async_get(device.id, include_child_devices=False)
    assert updated is not None
    assert updated.sw_version == "1.1"
    assert updated.hw_version == "2.0"
    assert mock_api.async_execute_command.await_count == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_ID, "heat")
    mock_climate_api.async_get_current_temperature.assert_awaited_once()
    assert mock_api.async_execute_command.await_count == 2

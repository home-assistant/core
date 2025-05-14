"""Tests for the nut integration."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_fixture


def _get_mock_nutclient(
    list_vars=None,
    list_ups=None,
    list_commands_return_value=None,
    list_commands_side_effect=None,
    run_command=None,
):
    nutclient = MagicMock()
    type(nutclient).list_ups = AsyncMock(return_value=list_ups)
    type(nutclient).list_vars = AsyncMock(return_value=list_vars)
    if list_commands_return_value is None:
        list_commands_return_value = {}
    type(nutclient).list_commands = AsyncMock(
        return_value=list_commands_return_value, side_effect=list_commands_side_effect
    )
    if run_command is None:
        run_command = AsyncMock()
    type(nutclient).run_command = run_command
    return nutclient


async def async_init_integration(
    hass: HomeAssistant,
    ups_fixture: str | None = None,
    host: str = "mock",
    port: int = 1234,
    username: str = "mock",
    password: str = "mock",
    alias: str | None = None,
    list_ups: dict[str, str] | None = None,
    list_vars: dict[str, str] | None = None,
    list_commands_return_value: dict[str, str] | None = None,
    list_commands_side_effect=None,
    run_command: MagicMock | None = None,
) -> MockConfigEntry:
    """Set up the nut integration in Home Assistant."""

    if list_ups is None:
        list_ups = {"ups1": "UPS 1"}

    if ups_fixture is not None:
        ups_fixture = f"nut/{ups_fixture}.json"
        if list_vars is None:
            list_vars = json.loads(load_fixture(ups_fixture))

    mock_pynut = _get_mock_nutclient(
        list_ups=list_ups,
        list_vars=list_vars,
        list_commands_return_value=list_commands_return_value,
        list_commands_side_effect=list_commands_side_effect,
        run_command=run_command,
    )

    with patch(
        "homeassistant.components.nut.AIONUTClient",
        return_value=mock_pynut,
    ):
        extra_config_entry_data: dict[str, Any] = {}

        if alias is not None:
            extra_config_entry_data = {
                CONF_ALIAS: alias,
            }

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: host,
                CONF_PASSWORD: password,
                CONF_PORT: port,
                CONF_USERNAME: username,
            }
            | extra_config_entry_data,
        )

        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _test_sensor_and_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    unique_id: str,
    device_id: str,
    state_value: str,
    expected_attributes: dict,
) -> None:
    """Test all of the sensor entry attributes."""

    entry = entity_registry.async_get(device_id)
    assert entry
    assert entry.unique_id == unique_id

    state = hass.states.get(device_id)
    assert state.state == state_value

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == attr for key, attr in expected_attributes.items()
    )

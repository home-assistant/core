"""Tests for the nut integration."""

import json
from unittest.mock import MagicMock, patch

from homeassistant.components.nut.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def _get_mock_pynutclient(
    list_vars=None,
    list_ups=None,
    list_commands_return_value=None,
    list_commands_side_effect=None,
    run_command=None,
):
    pynutclient = MagicMock()
    type(pynutclient).list_ups = MagicMock(return_value=list_ups)
    type(pynutclient).list_vars = MagicMock(return_value=list_vars)
    if list_commands_return_value is None:
        list_commands_return_value = {}
    type(pynutclient).list_commands = MagicMock(
        return_value=list_commands_return_value, side_effect=list_commands_side_effect
    )
    if run_command is None:
        run_command = MagicMock()
    type(pynutclient).run_command = run_command
    return pynutclient


async def async_init_integration(
    hass: HomeAssistant,
    ups_fixture: str = None,
    username: str = "mock",
    password: str = "mock",
    list_ups: dict[str, str] = None,
    list_vars: dict[str, str] = None,
    list_commands_return_value: dict[str, str] = None,
    list_commands_side_effect=None,
    run_command: MagicMock = None,
) -> MockConfigEntry:
    """Set up the nut integration in Home Assistant."""

    if list_ups is None:
        list_ups = {"ups1": "UPS 1"}

    if ups_fixture is not None:
        ups_fixture = f"nut/{ups_fixture}.json"
        if list_vars is None:
            list_vars = json.loads(load_fixture(ups_fixture))

    mock_pynut = _get_mock_pynutclient(
        list_ups=list_ups,
        list_vars=list_vars,
        list_commands_return_value=list_commands_return_value,
        list_commands_side_effect=list_commands_side_effect,
        run_command=run_command,
    )

    with patch(
        "homeassistant.components.nut.PyNUTClient",
        return_value=mock_pynut,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "mock",
                CONF_PASSWORD: password,
                CONF_PORT: "mock",
                CONF_USERNAME: username,
            },
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry

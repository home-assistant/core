"""Test integration behavior through the released OpenGarage client."""

import re

import pytest

from homeassistant.components.opengarage.const import CONF_DEVICE_KEY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    ("door", "service", "command"),
    [
        pytest.param(0, "open_cover", "open", id="open"),
        pytest.param(1, "close_cover", "close", id="close"),
    ],
)
async def test_public_command_encoding(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    door: int,
    service: str,
    command: str,
) -> None:
    """The released client preserves reserved characters in device keys."""
    key = "abc123&=?/+ #"
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_DEVICE_KEY: key}
    )
    aioclient_mock.get(
        "http://1.1.1.1:80/jc",
        json={"name": "abcdef", "mac": "aa:bb:cc:dd:ee:ff", "fwv": 124, "door": door},
    )
    aioclient_mock.get(
        re.compile(r"http://1\.1\.1\.1(?::80)?/cc\?.*"), json={"result": 1}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "cover", service, {ATTR_ENTITY_ID: "cover.garage_abcdef"}, blocking=True
    )
    assert aioclient_mock.mock_calls[-1][1].query == {"dkey": key, command: "1"}
    assert aioclient_mock.call_count == 2

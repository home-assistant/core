"""The tests for the Mikrotik device tracker platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from librouteros import Api
from librouteros.exceptions import TrapError

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import ATTR_FIRMWARE, ATTR_MODEL
from homeassistant.components.mikrotik.hub import MikrotikData
from homeassistant.core import HomeAssistant

from . import MOCK_DATA

from tests.common import MockConfigEntry


async def test_info_routerboard(hass: HomeAssistant) -> None:
    """Test device firmware/model for routerboard routers."""
    entry_id = "mikrotik_entry_id"
    options: dict[str, Any] = {}
    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=options, entry_id=entry_id
    )

    api = MagicMock(Api)
    api.return_value = [{ATTR_FIRMWARE: "test_firmware", ATTR_MODEL: "test_model"}]
    mikrotik_data = MikrotikData(hass, config_entry, api)

    model = mikrotik_data.get_info(ATTR_MODEL)
    assert model == "test_model"

    firmware = mikrotik_data.get_info(ATTR_FIRMWARE)
    assert firmware == "test_firmware"

    assert mikrotik_data.is_routerboard is True

    assert api.call_count == 2


async def test_info_chr(hass: HomeAssistant) -> None:
    """Test device firmware/model for CHR routers."""
    entry_id = "mikrotik_entry_id"
    options: dict[str, Any] = {}
    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=options, entry_id=entry_id
    )

    api = MagicMock(Api)
    api.side_effect = TrapError(
        "no such command or directory (routerboard), no such command prefix"
    )
    mikrotik_data = MikrotikData(hass, config_entry, api)

    model = mikrotik_data.get_info(ATTR_MODEL)
    assert model == ""

    firmware = mikrotik_data.get_info(ATTR_FIRMWARE)
    assert firmware == ""

    assert mikrotik_data.is_routerboard is False

    api.assert_called_once()

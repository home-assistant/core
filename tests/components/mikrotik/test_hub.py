"""The tests for the Mikrotik device tracker platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from librouteros import Api
from librouteros.exceptions import TrapError
import pytest

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import ATTR_FIRMWARE, ATTR_MODEL
from homeassistant.components.mikrotik.hub import MikrotikData

from . import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def api():
    """Mock Mikrotik Api."""
    return MagicMock(Api)


@pytest.fixture
def mikrotik_data(hass, api):
    """Create MikrotikData."""
    entry_id = "mikrotik_entry_id"
    options: dict[str, Any] = {}
    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=options, entry_id=entry_id
    )
    return MikrotikData(hass, config_entry, api)


async def test_info_routerboard(mikrotik_data: MikrotikData, api: Api) -> None:
    """Test device firmware/model for routerboard routers."""
    api.return_value = [{ATTR_FIRMWARE: "test_firmware", ATTR_MODEL: "test_model"}]

    model = mikrotik_data.get_info(ATTR_MODEL)
    firmware = mikrotik_data.get_info(ATTR_FIRMWARE)

    assert model == "test_model"
    assert firmware == "test_firmware"
    assert mikrotik_data.is_routerboard is True
    assert api.call_count == 2


async def test_info_chr(mikrotik_data: MikrotikData, api: Api) -> None:
    """Test device firmware/model for CHR routers."""
    api.side_effect = TrapError(
        "no such command or directory (routerboard), no such command prefix"
    )

    model = mikrotik_data.get_info(ATTR_MODEL)
    firmware = mikrotik_data.get_info(ATTR_FIRMWARE)

    assert model == ""
    assert firmware == ""
    assert mikrotik_data.is_routerboard is False
    api.assert_called_once()

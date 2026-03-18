"""The tests for the wake on lan button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.wake_on_lan.const import CONF_BROADCAST_INTERFACE, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_MAC,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import DEFAULT_MAC

from tests.common import MockConfigEntry


async def test_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test button default state."""

    state = hass.states.get("button.wake_on_lan_00_01_02_03_04_05")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.wake_on_lan_00_01_02_03_04_05")
    assert entry
    assert entry.unique_id == "00:01:02:03:04:05"


async def test_service_calls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    loaded_entry: MockConfigEntry,
    mock_send_magic_packet: AsyncMock,
) -> None:
    """Test service call."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    freezer.move_to(now)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wake_on_lan_00_01_02_03_04_05"},
        blocking=True,
    )

    assert (
        hass.states.get("button.wake_on_lan_00_01_02_03_04_05").state == now.isoformat()
    )


async def test_service_calls_with_interface(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_send_magic_packet: AsyncMock,
) -> None:
    """Test service call with broadcast interface."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Wake on LAN {DEFAULT_MAC}",
        options={
            CONF_MAC: DEFAULT_MAC,
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 9,
            CONF_BROADCAST_INTERFACE: "192.168.1.5",
        },
        entry_id="2",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    freezer.move_to(now)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wake_on_lan_00_01_02_03_04_05"},
        blocking=True,
    )

    mock_send_magic_packet.assert_called_once_with(
        DEFAULT_MAC,
        ip_address="255.255.255.255",
        port=9,
        interface="192.168.1.5",
    )

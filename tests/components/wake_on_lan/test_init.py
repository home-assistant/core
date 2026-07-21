"""Tests for Wake On LAN component."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.wake_on_lan import DOMAIN, SERVICE_SEND_MAGIC_PACKET
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_send_magic_packet(hass: HomeAssistant) -> None:
    """Test of send magic packet service call."""
    with patch("homeassistant.components.wake_on_lan.wakeonlan") as mocked_wakeonlan:
        mac = "aa:bb:cc:dd:ee:ff"
        secureon_password = "00:aa:22:bb:33:cc"
        bc_ip = "192.168.255.255"
        bc_port = 999

        await async_setup_component(hass, DOMAIN, {})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_address": bc_ip, "broadcast_port": bc_port},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[0][1][0] == mac
        assert mocked_wakeonlan.mock_calls[0][2]["ip_address"] == bc_ip
        assert mocked_wakeonlan.mock_calls[0][2]["port"] == bc_port

        mocked_wakeonlan.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {
                "mac": mac,
                "secureon_password": secureon_password,
                "broadcast_address": bc_ip,
                "broadcast_port": bc_port,
            },
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[0][1][0] == f"{mac}/{secureon_password}"
        assert mocked_wakeonlan.mock_calls[0][2]["ip_address"] == bc_ip
        assert mocked_wakeonlan.mock_calls[0][2]["port"] == bc_port

        mocked_wakeonlan.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_address": bc_ip},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[0][1][0] == mac
        assert mocked_wakeonlan.mock_calls[0][2]["ip_address"] == bc_ip
        assert "port" not in mocked_wakeonlan.mock_calls[0][2]

        mocked_wakeonlan.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_port": bc_port},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[0][1][0] == mac
        assert mocked_wakeonlan.mock_calls[0][2]["port"] == bc_port
        assert "ip_address" not in mocked_wakeonlan.mock_calls[0][2]

        mocked_wakeonlan.reset_mock()
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_MAGIC_PACKET,
                {"broadcast_address": bc_ip},
                blocking=True,
            )
        assert len(mocked_wakeonlan.mock_calls) == 0

        mocked_wakeonlan.reset_mock()
        await hass.services.async_call(
            DOMAIN, SERVICE_SEND_MAGIC_PACKET, {"mac": mac}, blocking=True
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[0][1][0] == mac
        assert not mocked_wakeonlan.mock_calls[0][2]

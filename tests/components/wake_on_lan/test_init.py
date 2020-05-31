"""Tests for Wake On LAN component."""
import pytest
import voluptuous as vol

from homeassistant.components.wake_on_lan import DOMAIN, SERVICE_SEND_MAGIC_PACKET
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_send_magic_packet(hass):
    """Test of send magic packet service call."""
    with patch("homeassistant.components.wake_on_lan.wakeonlan") as mocked_wakeonlan:
        mac = "aa:bb:cc:dd:ee:ff"
        bc_ip = "192.168.255.255"

        await async_setup_component(hass, DOMAIN, {})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_address": bc_ip},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert mocked_wakeonlan.mock_calls[-1][2]["ip_address"] == bc_ip

        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_MAGIC_PACKET,
                {"broadcast_address": bc_ip},
                blocking=True,
            )
        assert len(mocked_wakeonlan.mock_calls) == 1

        await hass.services.async_call(
            DOMAIN, SERVICE_SEND_MAGIC_PACKET, {"mac": mac}, blocking=True
        )
        assert len(mocked_wakeonlan.mock_calls) == 2
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert not mocked_wakeonlan.mock_calls[-1][2]

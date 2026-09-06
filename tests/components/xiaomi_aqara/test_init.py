"""Test the Xiaomi Aqara setup and device registry linking."""

from collections import defaultdict
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.xiaomi_aqara import const
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_PORT = 1234
TEST_PROTOCOL = "1.1.1"
TEST_MAC = "ab:cd:ef:00:11:22"
TEST_MOTION_SID = "158d0001a2b3c4"


async def test_child_device_links_to_gateway_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a Zigbee child device is linked to its gateway via via_device_id."""
    mock_gateway = Mock()
    mock_gateway.sid = TEST_MAC.replace(":", "").lower()
    mock_gateway.callbacks = defaultdict(list)
    mock_gateway.devices = {
        "binary_sensor": [
            {
                "sid": TEST_MOTION_SID,
                "model": "motion",
                "proto": TEST_PROTOCOL,
                "data": {},
                "raw_data": {"cmd": "report"},
            }
        ],
        "sensor": [],
    }

    mock_multicast = Mock()
    mock_multicast.start_listen = AsyncMock()
    mock_multicast.stop_listen = Mock()

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_MAC,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MAC: TEST_MAC,
            const.CONF_INTERFACE: "any",
            CONF_PROTOCOL: TEST_PROTOCOL,
            const.CONF_KEY: None,
            const.CONF_SID: mock_gateway.sid,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.xiaomi_aqara.XiaomiGateway",
            return_value=mock_gateway,
        ),
        patch(
            "homeassistant.components.xiaomi_aqara.AsyncXiaomiGatewayMulticast",
            return_value=mock_multicast,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    gateway_device = device_registry.async_get_device_by_identifier(
        (const.DOMAIN, TEST_MAC), entry.entry_id
    )
    child_device = device_registry.async_get_device_by_identifier(
        (const.DOMAIN, TEST_MOTION_SID), entry.entry_id
    )

    assert gateway_device is not None
    assert child_device is not None
    assert child_device.via_device_id == gateway_device.id

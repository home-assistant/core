"""Tests for gree component."""

from asyncio import DatagramTransport
from collections.abc import Callable
from datetime import datetime, timedelta
from ipaddress import IPv4Address
import json
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from greeclimate.cipher import CipherV1
from greeclimate.discovery import Discovery
from greeclimate.network import Response
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.components.gree.const import (
    CONF_KNOWN_HOSTS,
    DISCOVERY_SCAN_INTERVAL,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_setup_gree, build_device_mock

ENTITY_ID_1 = f"{CLIMATE_DOMAIN}.fake_device_1"
ENTITY_ID_2 = f"{CLIMATE_DOMAIN}.fake_device_2"
KNOWN_HOST_ENTITY_ID = f"{CLIMATE_DOMAIN}.known_host"
_BROADCAST_ENTITY_ID = f"{CLIMATE_DOMAIN}.broadcast_device"
_SECOND_BROADCAST_ENTITY_ID = f"{CLIMATE_DOMAIN}.second_broadcast_device"


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def test_discovery_after_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, discovery, device, mock_now
) -> None:
    """Test gree devices don't change after multiple discoveries."""
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )

    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    entry = await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 1
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in entry.runtime_data.coordinators]
    assert device_infos[0].ip == "1.1.1.1"
    assert device_infos[1].ip == "2.2.2.2"

    # rediscover the same devices with new ip addresses should update
    mock_device_1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.2", mac="aabbcc112233"
    )
    mock_device_2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.1", mac="bbccdd223344"
    )
    discovery.return_value.mock_devices = [mock_device_1, mock_device_2]
    device.side_effect = [mock_device_1, mock_device_2]

    next_update = mock_now + timedelta(minutes=6)
    freezer.move_to(next_update)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2

    device_infos = [x.device.device_info for x in entry.runtime_data.coordinators]
    assert device_infos[0].ip == "1.1.1.2"
    assert device_infos[1].ip == "2.2.2.1"


async def test_coordinator_updates(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test gree devices update their state."""
    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 1

    async def fake_update_state() -> None:
        """Fake update state."""
        device().power = True
        device().raw_properties["Pow"] = 1
        device().callbacks[Response.DATA]({"Pow": 1})

    device().update_state.side_effect = fake_update_state

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == HVACMode.AUTO


async def test_known_hosts_discovery_survives_reload(
    hass: HomeAssistant, discovery: MagicMock, device: MagicMock
) -> None:
    """Test real library discovery finds a configured target before and after reload."""
    host = "192.0.2.14"
    discovery.side_effect = Discovery
    device.return_value = build_device_mock(
        name="known-host", ipAddress=host, mac="bbccdd223344"
    )
    pack, _ = CipherV1().encrypt({"mac": "bbccdd223344", "name": "known-host"})
    response = json.dumps({"pack": pack}).encode()

    async def create_datagram_endpoint(
        protocol_factory: Callable[[], Discovery], **kwargs: object
    ) -> tuple[DatagramTransport, Discovery]:
        """Replace UDP I/O while running the real discovery protocol."""
        protocol = protocol_factory()
        transport = MagicMock(spec=DatagramTransport)
        protocol.connection_made(transport)

        def sendto(data: bytes, addr: tuple[str, int]) -> None:
            """Reply only to a scan directed at the configured target."""
            assert json.loads(data) == {"t": "scan"}
            if addr == (host, 7000):
                protocol.datagram_received(response, addr)

        transport.sendto.side_effect = sendto
        return transport, protocol

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_KNOWN_HOSTS: [host]})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.gree.async_get_ipv4_broadcast_addresses",
            return_value={IPv4Address("192.0.2.255")},
        ),
        patch.object(
            hass.loop, "create_datagram_endpoint", side_effect=create_datagram_endpoint
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert {
            state.entity_id: state.state
            for state in hass.states.async_all(CLIMATE_DOMAIN)
        } == {KNOWN_HOST_ENTITY_ID: HVACMode.OFF}

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.data[CONF_KNOWN_HOSTS] == [host]
    assert {
        state.entity_id: state.state for state in hass.states.async_all(CLIMATE_DOMAIN)
    } == {KNOWN_HOST_ENTITY_ID: HVACMode.OFF}


async def test_configure_known_hosts_and_clear_preserve_broadcast_discovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_now: datetime,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """Test target updates scan immediately without losing broadcast discovery."""
    host = "192.0.2.14"
    broadcast_address = IPv4Address("192.0.2.255")
    broadcast_device = build_device_mock(
        name="broadcast-device", ipAddress="192.0.2.10", mac="aabbcc112233"
    )
    known_host_device = build_device_mock(
        name="known-host", ipAddress=host, mac="bbccdd223344"
    )
    second_broadcast_device = build_device_mock(
        name="second-broadcast-device",
        ipAddress="192.0.2.11",
        mac="ccddee334455",
    )

    fake_discovery = discovery.return_value
    fake_discovery.mock_devices = [broadcast_device]
    fake_discovery.mock_devices_by_address[host] = [known_host_device]
    device.side_effect = [
        broadcast_device,
        known_host_device,
        second_broadcast_device,
    ]

    with patch(
        "homeassistant.components.gree.async_get_ipv4_broadcast_addresses",
        side_effect=lambda _hass: {broadcast_address},
    ):
        entry = await async_setup_gree(hass)
        await hass.async_block_till_done()
        assert {
            state.entity_id: state.state
            for state in hass.states.async_all(CLIMATE_DOMAIN)
        } == {_BROADCAST_ENTITY_ID: HVACMode.OFF}

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_KNOWN_HOSTS: [host]}
        )
        await hass.async_block_till_done()
        assert {
            state.entity_id: state.state
            for state in hass.states.async_all(CLIMATE_DOMAIN)
        } == {
            _BROADCAST_ENTITY_ID: HVACMode.OFF,
            KNOWN_HOST_ENTITY_ID: HVACMode.OFF,
        }

        next_update = mock_now + timedelta(seconds=DISCOVERY_SCAN_INTERVAL + 1)
        freezer.move_to(next_update)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
        assert {
            state.entity_id: state.state
            for state in hass.states.async_all(CLIMATE_DOMAIN)
        } == {
            _BROADCAST_ENTITY_ID: HVACMode.OFF,
            KNOWN_HOST_ENTITY_ID: HVACMode.OFF,
        }

        fake_discovery.mock_devices = []
        fake_discovery.mock_devices_by_address[host] = [
            build_device_mock(name="not-targeted", ipAddress=host, mac="ddeeff445566")
        ]
        fake_discovery.mock_devices_by_address[str(broadcast_address)] = [
            second_broadcast_device
        ]
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_KNOWN_HOSTS: []}
        )
        await hass.async_block_till_done()

    assert {
        state.entity_id: state.state for state in hass.states.async_all(CLIMATE_DOMAIN)
    } == {
        _BROADCAST_ENTITY_ID: HVACMode.OFF,
        KNOWN_HOST_ENTITY_ID: HVACMode.OFF,
        _SECOND_BROADCAST_ENTITY_ID: HVACMode.OFF,
    }

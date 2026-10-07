"""Tests for the lookin integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.lookin import UDP_MANAGER
from homeassistant.components.lookin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import DEVICE_ID, DEVICE_NAME, IP_ADDRESS, MODULE

from tests.common import MockConfigEntry

MEDIA_UUID = "9999"


def _mocked_device() -> MagicMock:
    device = MagicMock()
    device.name = DEVICE_NAME
    device.id = DEVICE_ID
    # A model < 2 device has no meteo sensor, so the lookin device is only
    # registered by async_setup_entry, not by a sibling sensor entity.
    device.model = 1
    device.firmware = "1.2.3"
    return device


def _mocked_remote() -> MagicMock:
    remote = MagicMock()
    remote.name = "Living Room TV"
    remote.device_type = "TV"
    remote.status = "1000"
    remote.functions = []
    return remote


def _mocked_protocol(device: MagicMock, remote: MagicMock) -> MagicMock:
    protocol = MagicMock()
    protocol.get_info = AsyncMock(return_value=device)
    protocol.get_devices = AsyncMock(return_value=[{"Type": "01", "UUID": MEDIA_UUID}])
    protocol.get_remote = AsyncMock(return_value=remote)
    protocol.get_media_sources = AsyncMock(return_value=[])
    protocol.send_command = AsyncMock()
    return protocol


async def test_controlled_device_links_to_lookin_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a controlled device links to the lookin device via via_device_id."""
    device = _mocked_device()
    remote = _mocked_remote()
    protocol = _mocked_protocol(device, remote)

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=DEVICE_ID
    )
    entry.add_to_hass(hass)

    subscriptions = MagicMock()
    subscriptions.subscribe_event = MagicMock(return_value=MagicMock())

    with (
        patch(f"{MODULE}.LookInHttpProtocol", return_value=protocol),
        patch(f"{MODULE}.LookinUDPSubscriptions", return_value=subscriptions),
        patch(f"{MODULE}.start_lookin_udp", AsyncMock(return_value=MagicMock())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    lookin_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), entry.entry_id
    )
    assert lookin_device is not None

    controlled_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MEDIA_UUID), entry.entry_id
    )
    assert controlled_device is not None
    assert controlled_device.via_device_id == lookin_device.id


async def test_udp_manager_outlives_the_config_entry(hass: HomeAssistant) -> None:
    """Test the shared UDP manager is reused rather than rebuilt per entry."""
    device = _mocked_device()
    remote = _mocked_remote()
    protocol = _mocked_protocol(device, remote)

    subscriptions = MagicMock()
    subscriptions.subscribe_event = MagicMock(return_value=MagicMock())

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=DEVICE_ID
    )
    entry.add_to_hass(hass)

    with (
        patch(f"{MODULE}.LookInHttpProtocol", return_value=protocol),
        patch(f"{MODULE}.LookinUDPSubscriptions", return_value=subscriptions),
        patch(f"{MODULE}.start_lookin_udp", AsyncMock(return_value=MagicMock())),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        manager = hass.data[UDP_MANAGER]
        assert manager is not None

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # The manager is keyed globally, not on the entry, so a reload reuses it
    # instead of leaving a second listener behind.
    assert hass.data[UDP_MANAGER] is manager

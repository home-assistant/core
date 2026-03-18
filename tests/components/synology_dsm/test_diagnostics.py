"""Test Synology DSM diagnostics."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from synology_dsm.api.core.external_usb import SynoCoreExternalUSBDevice
from synology_dsm.api.dsm.network import NetworkInterface
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .common import mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def mock_dsm_with_usb():
    """Mock a successful service with USB support."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade = Mock(
            update_available=False,
            available_version=None,
            reboot_needed=None,
            service_restarts=None,
            update=AsyncMock(return_value=True),
        )
        dsm.utilisation = Mock(
            cpu={
                "15min_load": 461,
                "1min_load": 410,
                "5min_load": 404,
                "device": "System",
                "other_load": 5,
                "system_load": 11,
                "user_load": 11,
            },
            memory={
                "avail_real": 463628,
                "avail_swap": 0,
                "buffer": 10556600,
                "cached": 5297776,
                "device": "Memory",
                "memory_size": 33554432,
                "real_usage": 50,
                "si_disk": 0,
                "so_disk": 0,
                "swap_usage": 100,
                "total_real": 32841680,
                "total_swap": 2097084,
            },
            network=[
                {"device": "total", "rx": 1065612, "tx": 36311},
                {"device": "eth0", "rx": 1065612, "tx": 36311},
            ],
            memory_available_swap=Mock(return_value=0),
            memory_available_real=Mock(return_value=463628),
            memory_total_swap=Mock(return_value=2097084),
            memory_total_real=Mock(return_value=32841680),
            network_up=Mock(return_value=1065612),
            network_down=Mock(return_value=36311),
            update=AsyncMock(return_value=True),
        )
        dsm.network = Mock(
            update=AsyncMock(return_value=True),
            macs=MACS,
            hostname=HOST,
            interfaces=[
                NetworkInterface(
                    {
                        "id": "ovs_eth0",
                        "ip": [{"address": "127.0.0.1", "netmask": "255.255.255.0"}],
                        "type": "ovseth",
                    }
                )
            ],
        )
        dsm.information = mock_dsm_information()
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        dsm.external_usb = Mock(
            update=AsyncMock(return_value=True),
            get_device=Mock(
                return_value=SynoCoreExternalUSBDevice(
                    {
                        "dev_id": "usb1",
                        "dev_type": "usbDisk",
                        "dev_title": "USB Disk 1",
                        "producer": "Western Digital Technologies, Inc.",
                        "product": "easystore 264D",
                        "formatable": True,
                        "progress": "",
                        "status": "normal",
                        "total_size_mb": 15259648,
                        "partitions": [
                            {
                                "dev_fstype": "ntfs",
                                "filesystem": "ntfs",
                                "name_id": "usb1p1",
                                "partition_title": "USB Disk 1 Partition 1",
                                "share_name": "usbshare1",
                                "status": "normal",
                                "total_size_mb": 15259646,
                                "used_size_mb": 5942441,
                            }
                        ],
                    }
                )
            ),
            get_devices={
                "usb1": SynoCoreExternalUSBDevice(
                    {
                        "dev_id": "usb1",
                        "dev_type": "usbDisk",
                        "dev_title": "USB Disk 1",
                        "producer": "Western Digital Technologies, Inc.",
                        "product": "easystore 264D",
                        "formatable": True,
                        "progress": "",
                        "status": "normal",
                        "total_size_mb": 15259648,
                        "partitions": [
                            {
                                "dev_fstype": "ntfs",
                                "filesystem": "ntfs",
                                "name_id": "usb1p1",
                                "partition_title": "USB Disk 1 Partition 1",
                                "share_name": "usbshare1",
                                "status": "normal",
                                "total_size_mb": 15259646,
                                "used_size_mb": 5942441,
                            }
                        ],
                    }
                )
            },
        )
        dsm.logout = AsyncMock(return_value=True)
        yield dsm


@pytest.fixture
async def setup_dsm_with_usb(
    hass: HomeAssistant,
    mock_dsm_with_usb: MagicMock,
):
    """Mock setup of synology dsm config entry with USB."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=mock_dsm_with_usb,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id=SERIAL,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        yield mock_dsm_with_usb


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_dsm_with_usb: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for Synology DSM config entry."""
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot(
        exclude=props("api_details", "created_at", "modified_at", "entry_id")
    )

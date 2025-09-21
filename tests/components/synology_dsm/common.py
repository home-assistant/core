"""Configure Synology DSM tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from awesomeversion import AwesomeVersion
from synology_dsm.api.core.external_usb import SynoCoreExternalUSBDevice
from synology_dsm.api.storage.storage import SynoStorageDisk, SynoStorageVolume

from .consts import SERIAL


def mock_dsm_information(
    serial: str | None = SERIAL,
    update_result: bool = True,
    awesome_version: str = "7.2.2",
    model: str = "DS1821+",
    version_string: str = "DSM 7.2.2-72806 Update 3",
    ram: int = 32768,
    temperature: int = 58,
    uptime: int = 123456,
) -> Mock:
    """Mock SynologyDSM information."""
    return Mock(
        serial=serial,
        update=AsyncMock(return_value=update_result),
        awesome_version=AwesomeVersion(awesome_version),
        model=model,
        version_string=version_string,
        ram=ram,
        temperature=temperature,
        uptime=uptime,
    )


def mock_dsm_storage_get_volume(volume_id: str) -> SynoStorageVolume:
    """Mock SynologyDSM storage volume information for a specific volume."""
    volumes = mock_dsm_storage_volumes()
    for volume in volumes:
        if volume.get("id") == volume_id:
            return volume
    raise ValueError(f"Volume with id {volume_id} not found in mock data.")


def mock_dsm_storage_volumes() -> list[SynoStorageVolume]:
    """Mock SynologyDSM storage volume information."""
    volumes_data = {
        "volume_1": {
            "id": "volume_1",
            "device_type": "btrfs",
            "size": {
                "free_inode": "1000000",
                "total": "24000277250048",
                "total_device": "24000277250048",
                "total_inode": "2000000",
                "used": "12000138625024",
            },
            "status": "normal",
            "fs_type": "btrfs",
        },
    }
    return [SynoStorageVolume(**volume_info) for volume_info in volumes_data.values()]


def mock_dsm_storage_get_disk(disk_id: str) -> SynoStorageDisk:
    """Mock SynologyDSM storage disk information for a specific disk."""
    disks = mock_dsm_storage_disks()
    for disk in disks:
        if disk.get("id") == disk_id:
            return disk
    raise ValueError(f"Disk with id {disk_id} not found in mock data.")


def mock_dsm_storage_disks() -> list[SynoStorageDisk]:
    """Mock SynologyDSM storage disk information."""
    disks_data = {
        "sata1": {
            "id": "sata1",
            "name": "Drive 1",
            "vendor": "Seagate",
            "model": "ST24000NT002-3N1101",
            "device": "/dev/sata1",
            "temp": 32,
            "size_total": "24000277250048",
            "firm": "EN01",
            "diskType": "SATA",
        },
        "sata2": {
            "id": "sata2",
            "name": "Drive 2",
            "vendor": "Seagate",
            "model": "ST24000NT002-3N1101",
            "device": "/dev/sata2",
            "temp": 32,
            "size_total": "24000277250048",
            "firm": "EN01",
            "diskType": "SATA",
        },
        "sata3": {
            "id": "sata3",
            "name": "Drive 3",
            "vendor": "Seagate",
            "model": "ST24000NT002-3N1101",
            "device": "/dev/sata3",
            "temp": 32,
            "size_total": "24000277250048",
            "firm": "EN01",
            "diskType": "SATA",
        },
    }
    return [SynoStorageDisk(**disk_info) for disk_info in disks_data.values()]


def mock_dsm_external_usb_devices_usb1() -> dict[str, SynoCoreExternalUSBDevice]:
    """Mock SynologyDSM external USB device with USB Disk 1."""
    return {
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
                        "share_name": "usbshare2",
                        "status": "normal",
                        "total_size_mb": 15259646,
                        "used_size_mb": 5942441,
                    }
                ],
            }
        ),
    }


def mock_dsm_external_usb_devices_usb2() -> dict[str, SynoCoreExternalUSBDevice]:
    """Mock SynologyDSM external USB device with USB Disk 1 and USB Disk 2."""
    return {
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
                        "share_name": "usbshare2",
                        "status": "normal",
                        "total_size_mb": 15259646,
                        "used_size_mb": 5942441,
                    }
                ],
            }
        ),
        "usb2": SynoCoreExternalUSBDevice(
            {
                "dev_id": "usb2",
                "dev_type": "usbDisk",
                "dev_title": "USB Disk 2",
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
                        "name_id": "usb2p1",
                        "partition_title": "USB Disk 2 Partition 1",
                        "share_name": "usbshare2",
                        "status": "normal",
                        "total_size_mb": 15259646,
                        "used_size_mb": 5942441,
                    }
                ],
            }
        ),
    }

"""Tests for Synology DSM USB."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from synology_dsm.api.core.external_usb import SynoCoreExternalUSBDevice

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
from homeassistant.helpers import entity_registry as er

from .common import mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_dsm_with_usb():
    """Mock a successful service with USB support."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
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
def mock_dsm_without_usb():
    """Mock a successful service without USB devices."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
        )
        dsm.information = mock_dsm_information()
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
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


@pytest.fixture
async def setup_dsm_without_usb(
    hass: HomeAssistant,
    mock_dsm_without_usb: MagicMock,
):
    """Mock setup of synology dsm config entry without USB."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=mock_dsm_without_usb,
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

        yield mock_dsm_without_usb


async def test_external_usb(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_dsm_with_usb: MagicMock,
) -> None:
    """Test Synology DSM USB sensors."""
    # test disabled device size sensor
    entity_id = "sensor.nas_meontheinternet_com_usb_disk_1_device_size"
    entity_entry = entity_registry.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # test partition size sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_size"
    )
    assert sensor is not None
    assert sensor.state == "14901.998046875"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 1 Partition 1) Partition size"
    )
    assert sensor.attributes["device_class"] == "data_size"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "GiB"
    assert sensor.attributes["attribution"] == "Data provided by Synology"

    # test partition used space sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_used_space"
    )
    assert sensor is not None
    assert sensor.state == "5803.1650390625"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 1 Partition 1) Partition used space"
    )
    assert sensor.attributes["device_class"] == "data_size"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "GiB"
    assert sensor.attributes["attribution"] == "Data provided by Synology"

    # test partition used sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_used"
    )
    assert sensor is not None
    assert sensor.state == "38.9"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 1 Partition 1) Partition used"
    )
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "%"
    assert sensor.attributes["attribution"] == "Data provided by Synology"


async def test_no_external_usb(
    hass: HomeAssistant,
    setup_dsm_without_usb: MagicMock,
) -> None:
    """Test Synology DSM without USB."""
    sensor = hass.states.get("sensor.nas_meontheinternet_com_usb_disk_1_device_size")
    assert sensor is None

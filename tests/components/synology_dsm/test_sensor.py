"""Tests for Synology DSM USB."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    mock_dsm_external_usb_devices_usb1,
    mock_dsm_external_usb_devices_usb2,
    mock_dsm_information,
    mock_dsm_storage_get_disk,
    mock_dsm_storage_get_volume,
)
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed


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
        dsm.storage = Mock(
            get_disk=mock_dsm_storage_get_disk,
            disk_temp=Mock(return_value=32),
            disks_ids=["sata1", "sata2", "sata3"],
            get_volume=mock_dsm_storage_get_volume,
            volume_disk_temp_avg=Mock(return_value=32),
            volume_size_used=Mock(return_value=12000138625024),
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        dsm.external_usb = Mock(
            update=AsyncMock(return_value=True),
            get_devices=mock_dsm_external_usb_devices_usb1(),
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


async def test_external_usb_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    setup_dsm_with_usb: MagicMock,
) -> None:
    """Test Synology DSM USB sensors availability."""

    # Coordinator refresh
    # Mock the get_devices method to simulate a USB disk being removed and another being added
    setup_dsm_with_usb.external_usb.get_devices = mock_dsm_external_usb_devices_usb2()
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Test USB Disk 1 status sensor is unavailable
    sensor = hass.states.get("sensor.nas_meontheinternet_com_usb_disk_1_status")
    assert sensor is not None
    assert sensor.state == STATE_UNAVAILABLE

    # Test USB Disk 1 Partition 1 size sensor is unavailable
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_size"
    )
    assert sensor is not None
    assert sensor.state == STATE_UNAVAILABLE

    # Test USB Disk 1 Partition 1 partition used space sensor is unavailable
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_used_space"
    )
    assert sensor is not None
    assert sensor.state == STATE_UNAVAILABLE

    # Test USB Disk 1 Partition 1 partition used sensor is unavailable
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_1_partition_1_partition_used"
    )
    assert sensor is not None
    assert sensor.state == STATE_UNAVAILABLE

    # Test USB Disk 2 status sensor
    sensor = hass.states.get("sensor.nas_meontheinternet_com_usb_disk_2_status")
    assert sensor is not None
    assert sensor.state == "normal"

    # Test USB Disk 2 Partition 1 partition size sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_2_partition_1_partition_size"
    )
    assert sensor is not None
    assert sensor.state == "14901.998046875"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 2 Partition 1) Partition size"
    )
    assert sensor.attributes["device_class"] == "data_size"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "GiB"
    assert sensor.attributes["attribution"] == "Data provided by Synology"

    # Test USB Disk 2 Partition 1 partition used space sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_2_partition_1_partition_used_space"
    )
    assert sensor is not None
    assert sensor.state == "5803.1650390625"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 2 Partition 1) Partition used space"
    )
    assert sensor.attributes["device_class"] == "data_size"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "GiB"
    assert sensor.attributes["attribution"] == "Data provided by Synology"

    # Test USB Disk 2 Partition 1 partition used sensor
    sensor = hass.states.get(
        "sensor.nas_meontheinternet_com_usb_disk_2_partition_1_partition_used"
    )
    assert sensor is not None
    assert sensor.state == "38.9"
    assert (
        sensor.attributes["friendly_name"]
        == "nas.meontheinternet.com (USB Disk 2 Partition 1) Partition used"
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

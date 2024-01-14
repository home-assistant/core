"""Test System Monitor utils."""

from unittest.mock import Mock, patch

from psutil._common import sdiskpart
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (PermissionError("No permission"), "No permission for running user to access"),
        (OSError("OS error"), "was excluded because of: OS error"),
    ],
)
async def test_disk_setup_failure(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_util: Mock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error_text: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the disk failures."""

    with patch(
        "homeassistant.components.systemmonitor.util.psutil.disk_usage",
        side_effect=side_effect,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        disk_sensor = hass.states.get("sensor.system_monitor_disk_free_media_share")
        assert disk_sensor is None

        assert error_text in caplog.text


async def test_disk_util(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_util: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the disk failures."""

    mock_util.disk_partitions.return_value = [
        sdiskpart("test", "/", "ext4", "", 1, 1),  # Should be ok
        sdiskpart("test2", "/media/share", "ext4", "", 1, 1),  # Should be ok
        sdiskpart("test3", "/incorrect", "", "", 1, 1),  # Should be skipped as no type
        sdiskpart(
            "proc", "/proc/run", "proc", "", 1, 1
        ),  # Should be skipped as in skipped disk types
        sdiskpart(
            "test4",
            "/tmpfs/",  # noqa: S108
            "tmpfs",
            "",
            1,
            1,
        ),  # Should be skipped as in skipped disk types
        sdiskpart("test5", "E:", "cd", "cdrom", 1, 1),  # Should be skipped as cdrom
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    disk_sensor1 = hass.states.get("sensor.system_monitor_disk_free")
    disk_sensor2 = hass.states.get("sensor.system_monitor_disk_free_media_share")
    disk_sensor3 = hass.states.get("sensor.system_monitor_disk_free_incorrect")
    disk_sensor4 = hass.states.get("sensor.system_monitor_disk_free_proc_run")
    disk_sensor5 = hass.states.get("sensor.system_monitor_disk_free_tmpfs")
    disk_sensor6 = hass.states.get("sensor.system_monitor_disk_free_e")
    assert disk_sensor1 is not None
    assert disk_sensor2 is not None
    assert disk_sensor3 is None
    assert disk_sensor4 is None
    assert disk_sensor5 is None
    assert disk_sensor6 is None

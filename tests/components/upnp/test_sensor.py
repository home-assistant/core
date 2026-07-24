"""Tests for UPnP/IGD sensor."""

from datetime import datetime, timedelta

from async_upnp_client.profiles.igd import IgdDevice, IgdState
import pytest

from homeassistant.components.upnp.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_upnp_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensors."""
    # First poll.
    assert hass.states.get("sensor.mock_name_data_received").state == "0"
    assert hass.states.get("sensor.mock_name_data_sent").state == "0"
    assert hass.states.get("sensor.mock_name_packets_received").state == "0"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "0"
    assert hass.states.get("sensor.mock_name_external_ip").state == "8.9.10.11"
    assert hass.states.get("sensor.mock_name_wan_status").state == "Connected"
    assert hass.states.get("sensor.mock_name_download_speed").state == "unknown"
    assert hass.states.get("sensor.mock_name_upload_speed").state == "unknown"
    assert hass.states.get("sensor.mock_name_packet_download_speed").state == "unknown"
    assert hass.states.get("sensor.mock_name_packet_upload_speed").state == "unknown"
    assert (
        hass.states.get("sensor.mock_name_download_speed_no_rollover_handling").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.mock_name_upload_speed_no_rollover_handling").state
        == "unknown"
    )
    assert (
        hass.states.get(
            "sensor.mock_name_packet_download_speed_no_rollover_handling"
        ).state
        == "unknown"
    )
    assert (
        hass.states.get(
            "sensor.mock_name_packet_upload_speed_no_rollover_handling"
        ).state
        == "unknown"
    )

    # Second poll.
    mock_igd_device: IgdDevice = mock_config_entry.igd_device
    mock_igd_device.async_get_traffic_and_status_data.return_value = IgdState(
        timestamp=datetime.now(),  # pylint: disable=home-assistant-enforce-naive-now
        bytes_received=10240,
        bytes_sent=20480,
        packets_received=30,
        packets_sent=40,
        connection_status="Disconnected",
        last_connection_error="",
        uptime=40,
        external_ip_address="",
        kibibytes_per_sec_received=10.0,
        kibibytes_per_sec_sent=20.0,
        packets_per_sec_received=30.0,
        packets_per_sec_sent=40.0,
        kibibytes_per_sec_received_no_rollover=10.0,
        kibibytes_per_sec_sent_no_rollover=20.0,
        packets_per_sec_received_no_rollover=30.0,
        packets_per_sec_sent_no_rollover=40.0,
        port_mapping_number_of_entries=0,
    )

    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_name_data_received").state == "10240"
    assert hass.states.get("sensor.mock_name_data_sent").state == "20480"
    assert hass.states.get("sensor.mock_name_packets_received").state == "30"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "40"
    assert hass.states.get("sensor.mock_name_external_ip").state == ""
    assert hass.states.get("sensor.mock_name_wan_status").state == "Disconnected"
    assert hass.states.get("sensor.mock_name_download_speed").state == "10.0"
    assert hass.states.get("sensor.mock_name_upload_speed").state == "20.0"
    assert hass.states.get("sensor.mock_name_packet_download_speed").state == "30.0"
    assert hass.states.get("sensor.mock_name_packet_upload_speed").state == "40.0"
    assert (
        hass.states.get("sensor.mock_name_download_speed_no_rollover_handling").state
        == "10.0"
    )
    assert (
        hass.states.get("sensor.mock_name_upload_speed_no_rollover_handling").state
        == "20.0"
    )
    assert (
        hass.states.get(
            "sensor.mock_name_packet_download_speed_no_rollover_handling"
        ).state
        == "30.0"
    )
    assert (
        hass.states.get(
            "sensor.mock_name_packet_upload_speed_no_rollover_handling"
        ).state
        == "40.0"
    )


async def test_upnp_sensors_no_rollover_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no-rollover sensors are disabled by default and can be enabled."""
    disabled_entity_id = "sensor.mock_name_download_speed_no_rollover_handling"
    other_disabled_entity_ids = (
        "sensor.mock_name_upload_speed_no_rollover_handling",
        "sensor.mock_name_packet_download_speed_no_rollover_handling",
        "sensor.mock_name_packet_upload_speed_no_rollover_handling",
    )

    assert hass.states.get(disabled_entity_id) is None
    for entity_id in other_disabled_entity_ids:
        assert hass.states.get(entity_id) is None

    entry = entity_registry.async_get(disabled_entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    for entity_id in other_disabled_entity_ids:
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(disabled_entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    enabled_state = hass.states.get(disabled_entity_id)
    assert enabled_state is not None
    assert enabled_state.state == "unknown"

"""Tests for QNAP sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


# ---------------------------------------------------------------------------
# Drive temperature sensor
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_drive_temp_sensor_none_returns_unknown(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Drive temp sensor must return None (unknown), NOT 0, when temp_c is None."""
    mock_qnap_client.get_smart_disk_health.return_value = {
        "HDD 1": {
            "health": "good",
            "temp_c": None,
            "drive_number": "0",
            "model": "TOSHIBA HDWD110",
            "serial": "X8ABC12345",
            "type": "HDD",
        }
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_nas_drive_hdd_1_temperature")
    assert state is not None
    assert state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE), (
        f"Expected unknown/unavailable for None temp, got: {state.state!r}"
    )
    assert state.state != "0", "drive_temp must not return 0 when temp_c is None"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_drive_temp_sensor_with_value(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Drive temp sensor returns the integer temperature when temp_c is set."""
    mock_qnap_client.get_smart_disk_health.return_value = {
        "HDD 1": {
            "health": "good",
            "temp_c": 38,
            "drive_number": "0",
            "model": "TOSHIBA HDWD110",
            "serial": "X8ABC12345",
            "type": "HDD",
        }
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_nas_drive_hdd_1_temperature")
    assert state is not None
    assert state.state == "38"


# ---------------------------------------------------------------------------
# Network bandwidth sensors
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_network_sensor_nic_missing_from_bandwidth(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Network tx/rx sensors return None when NIC absent from bandwidth data."""
    # eth0 is in system_stats/nics but NOT in bandwidth
    mock_qnap_client.get_bandwidth.return_value = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    tx_state = hass.states.get("sensor.test_nas_eth0_upload")
    rx_state = hass.states.get("sensor.test_nas_eth0_download")

    assert tx_state is not None, "network_tx sensor entity should exist"
    assert tx_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE), (
        f"Expected unknown/unavailable for missing bandwidth, got tx={tx_state.state!r}"
    )

    assert rx_state is not None, "network_rx sensor entity should exist"
    assert rx_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE), (
        f"Expected unknown/unavailable for missing bandwidth, got rx={rx_state.state!r}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_network_sensor_nic_in_bandwidth(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Network tx/rx sensors return a valid value when NIC is present in bandwidth."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    tx_state = hass.states.get("sensor.test_nas_eth0_upload")
    rx_state = hass.states.get("sensor.test_nas_eth0_download")

    assert tx_state is not None
    assert tx_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN), (
        f"Expected a valid bandwidth value for tx, got: {tx_state.state!r}"
    )

    assert rx_state is not None
    assert rx_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN), (
        f"Expected a valid bandwidth value for rx, got: {rx_state.state!r}"
    )

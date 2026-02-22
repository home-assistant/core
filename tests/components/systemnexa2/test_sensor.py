"""Test the System Nexa 2 sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sn2 import InformationData, InformationUpdate, StateChange
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test the sensor entities."""
    mock_config_entry.add_to_hass(hass)

    # Only load the sensor platform for snapshot testing
    with patch(
        "homeassistant.components.systemnexa2.PLATFORMS",
        [Platform.SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device,
) -> None:
    """Test sensor values are correctly displayed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check WiFi signal strength sensor
    state = hass.states.get("sensor.outdoor_smart_plug_wifi_signal_strength")
    assert state is not None
    assert state.state == "-50"

    # Check WiFi SSID sensor
    state = hass.states.get("sensor.outdoor_smart_plug_wifi_ssid")
    assert state is not None
    assert state.state == "Test WiFi SSID"


@pytest.mark.parametrize(
    ("wifi_dbm", "wifi_ssid"),
    [
        (None, None),
        (None, "Test WiFi"),
        (-50, None),
    ],
)
async def test_sensor_missing_data(
    hass: HomeAssistant,
    wifi_dbm: int | None,
    wifi_ssid: str | None,
) -> None:
    """Test sensors are not created when data is missing."""
    with (
        patch(
            "homeassistant.components.systemnexa2.coordinator.Device", autospec=True
        ) as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name="Test Device",
            model="Test Model",
            unique_id="test_device_id",
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=wifi_dbm,
            wifi_ssid=wifi_ssid,
            dimmable=False,
        )
        device.settings = []
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(information=device.info_data)

        async def mock_connect():
            """Mock connect that sends initial state."""
            if mock_device.initiate_device.call_args:
                on_update = mock_device.initiate_device.call_args.kwargs.get(
                    "on_update"
                )
                if on_update:
                    await on_update(StateChange(state=1.0))

        device.connect = AsyncMock(side_effect=mock_connect)
        device.disconnect = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))
        mock_device.initiate_device = AsyncMock(return_value=device)

        mock_config_entry = MockConfigEntry(
            domain="systemnexa2",
            unique_id="test_device_id",
            data={
                CONF_HOST: "10.0.0.100",
                CONF_NAME: "Test Device",
                CONF_DEVICE_ID: "test_device_id",
                CONF_MODEL: "Test Model",
            },
        )
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check if WiFi signal strength sensor exists
        state = hass.states.get("sensor.test_device_wifi_signal_strength")
        if wifi_dbm is None:
            assert state is None
        else:
            assert state is not None

        # Check if WiFi SSID sensor exists
        state = hass.states.get("sensor.test_device_wifi_ssid")
        if wifi_ssid is None:
            assert state is None
        else:
            assert state is not None

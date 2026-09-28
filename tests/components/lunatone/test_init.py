"""Tests for the Lunatone integration."""

from unittest.mock import AsyncMock, PropertyMock

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client.models.info import Tier
import pytest

from homeassistant.components.lunatone.const import DOMAIN, MANUFACTURER
from homeassistant.components.lunatone.coordinator import (
    DEFAULT_DEVICES_UPDATE_INTERVAL,
    DEFAULT_INFO_UPDATE_INTERVAL,
    DEFAULT_SENSORS_UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    BASE_URL,
    PRODUCT_NAME,
    SERIAL_NUMBER,
    UUID,
    VERSION,
    build_info_data,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.unique_id

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.manufacturer == MANUFACTURER
    assert device_entry.sw_version == VERSION
    assert device_entry.configuration_url == BASE_URL
    assert device_entry.model == PRODUCT_NAME

    for line_id in mock_lunatone_info.data.lines:
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{mock_config_entry.unique_id}-line{line_id}"),
            mock_config_entry.entry_id,
        )
        assert device_entry is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("tier", "emergency_light", "sensors_supported"),
    [
        (Tier.BASIC, False, True),
        (Tier.BASIC, True, False),
        (Tier.PLUS, False, True),
        (Tier.PLUS, True, True),
    ],
    ids=["basic", "emergency", "plus", "plus+emergency"],
)
async def test_load_config_entry_sensor_capability(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    tier: Tier,
    emergency_light: bool,
    sensors_supported: bool,
) -> None:
    """Test the sensor coordinator follows the device capabilities."""
    mock_lunatone_info.data.tier = tier
    mock_lunatone_info.data.emergency_light = emergency_light

    await setup_integration(hass, mock_config_entry)

    assert (
        mock_config_entry.runtime_data.coordinator_sensors is not None
    ) == sensors_supported
    if sensors_supported:
        mock_lunatone_sensors.async_refresh.assert_called()
        mock_lunatone_sensors.async_update.assert_called()
    else:
        mock_lunatone_sensors.async_refresh.assert_not_called()
        mock_lunatone_sensors.async_update.assert_not_called()


async def test_config_entry_not_ready_info_api_fail(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready due to info API failure."""
    mock_lunatone_info.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_info.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_devices_api_fail(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready due to devices API failure."""
    mock_lunatone_devices.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    mock_lunatone_devices.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_devices.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    mock_lunatone_devices.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_sensors_api_fail(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready due to sensors API failure."""
    mock_lunatone_sensors.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    mock_lunatone_devices.async_update.assert_called_once()
    mock_lunatone_sensors.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_sensors.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    mock_lunatone_devices.async_update.assert_called()
    mock_lunatone_sensors.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_scan_api_fail(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready due to sensors API failure."""
    mock_lunatone_scan.async_update.side_effect = aiohttp.ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    mock_lunatone_devices.async_update.assert_called_once()
    mock_lunatone_scan.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_lunatone_scan.async_update.side_effect = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_lunatone_info.async_update.assert_called()
    mock_lunatone_devices.async_update.assert_called()
    mock_lunatone_scan.async_update.assert_called()
    mock_lunatone_sensors.async_update.assert_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_not_ready_no_info_data(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready due to missing info data."""
    mock_lunatone_info.data = None

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_setup_error_no_info_data(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Lunatone config entry setup error due to missing info data."""
    info_data = build_info_data()
    type(mock_lunatone_info).data = PropertyMock(
        side_effect=[info_data, info_data, None]
    )

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_info.async_update.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_config_entry_unique_id_update(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Lunatone config entry migration to be successful."""
    config_entry = MockConfigEntry(
        title=BASE_URL,
        domain=DOMAIN,
        data={CONF_URL: BASE_URL},
        unique_id=str(SERIAL_NUMBER),
    )

    expected_unique_id = str(SERIAL_NUMBER)
    mock_lunatone_info.data.uid = None

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == expected_unique_id

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    for device in devices:
        for identifier in device.identifiers:
            assert identifier[1].startswith(expected_unique_id)

    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entity in entities:
        assert entity.unique_id.startswith(expected_unique_id)

    expected_unique_id = UUID.replace("-", "")
    mock_lunatone_info.data.uid = UUID

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == expected_unique_id

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    for device in devices:
        for identifier in device.identifiers:
            assert identifier[1].startswith(expected_unique_id)

    entities = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entity in entities:
        assert entity.unique_id.startswith(expected_unique_id)


async def test_coordinators_remove_stale_devices(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinators remove stale devices."""
    await setup_integration(hass, mock_config_entry)

    unique_id = mock_config_entry.unique_id
    assert unique_id is not None

    mock_lunatone_info.data.lines.pop("1")

    freezer.tick(DEFAULT_INFO_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{unique_id}-line1"), mock_config_entry.entry_id
    )
    assert device_entry is None

    mock_lunatone_devices.data.devices = [
        device for device in mock_lunatone_devices.data.devices if device.id != 6
    ]

    freezer.tick(DEFAULT_DEVICES_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{unique_id}-device6"), mock_config_entry.entry_id
    )
    assert device_entry is None

    mock_lunatone_sensors.data.sensors = [
        sensor for sensor in mock_lunatone_sensors.data.sensors if sensor.id != 3
    ]

    freezer.tick(DEFAULT_SENSORS_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{unique_id}-line0-d24-address0"),
        mock_config_entry.entry_id,
    )
    assert device_entry is None

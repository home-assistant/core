"""Tests for the AirGradient integration."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from airgradient import AirGradientError, ApiVersion
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.components.airgradient.coordinator import V1_CONFIG_APPLY_DELAY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import load_config_fixture, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    airgradient_devices: AsyncMock,
    airgradient_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, airgradient_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, airgradient_config_entry.unique_id),
        airgradient_config_entry.entry_id,
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_go_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Go device registry entry."""
    mock_v1_airgradient_client.get_config.return_value = load_config_fixture(
        "config_v1_local.json", ApiVersion.V1
    )
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_diy_legacy_entities(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DIY retains its legacy display entities."""
    mock_airgradient_client.get_current_measures.return_value.model = "DIY"
    with patch(
        "homeassistant.components.airgradient.PLATFORMS",
        [Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "number.airgradient_display_brightness",
        "select.airgradient_display_pm_standard",
        "select.airgradient_display_temperature_unit",
        "sensor.airgradient_display_brightness",
        "sensor.airgradient_display_pm_standard",
        "sensor.airgradient_display_temperature_unit",
        "button.airgradient_calibrate_co2_sensor",
    ):
        assert hass.states.get(entity_id) is not None

    for entity_id in (
        "number.airgradient_led_bar_brightness",
        "select.airgradient_led_bar_mode",
        "sensor.airgradient_led_bar_brightness",
        "sensor.airgradient_led_bar_mode",
        "button.airgradient_test_led_bar",
    ):
        assert hass.states.get(entity_id) is None


async def test_v1_config_refresh_skips_pending_writes(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_apply_delay: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test V1 config refreshes skip reads during pending writes."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    release_writes = asyncio.Event()
    first_write_started = asyncio.Event()
    second_write_started = asyncio.Event()

    async def write_config(started: asyncio.Event) -> None:
        started.set()
        await release_writes.wait()

    first_write = hass.async_create_task(
        coordinator.async_execute_config_write(write_config(first_write_started))
    )
    await first_write_started.wait()
    second_write = hass.async_create_task(
        coordinator.async_execute_config_write(write_config(second_write_started))
    )
    await second_write_started.wait()
    config_calls = mock_v1_airgradient_client.get_config.call_count

    await coordinator.async_refresh()

    assert mock_v1_airgradient_client.get_config.call_count == config_calls

    release_writes.set()
    await asyncio.gather(first_write, second_write)

    assert mock_config_apply_delay.await_count == 2
    assert mock_v1_airgradient_client.get_config.call_count == config_calls + 1


@pytest.mark.usefixtures("mock_config_apply_delay")
async def test_v1_successful_write_refreshes_when_concurrent_write_fails(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an accepted V1 write refreshes after another write fails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    failed_write_started = asyncio.Event()
    release_failed_write = asyncio.Event()

    async def fail_config_write() -> None:
        failed_write_started.set()
        await release_failed_write.wait()
        raise AirGradientError

    config_calls = mock_v1_airgradient_client.get_config.call_count
    failed_write = hass.async_create_task(
        coordinator.async_execute_config_write(fail_config_write())
    )
    await failed_write_started.wait()

    await coordinator.async_execute_config_write(asyncio.sleep(0))

    assert mock_v1_airgradient_client.get_config.call_count == config_calls

    release_failed_write.set()
    with pytest.raises(AirGradientError):
        await failed_write

    assert mock_v1_airgradient_client.get_config.call_count == config_calls + 1


async def test_v1_config_refresh_discards_in_flight_read(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_apply_delay: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a V1 config write discards an in-flight config read."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    cached_config = coordinator.data.config
    config_read_started = asyncio.Event()
    release_config_read = asyncio.Event()
    stale_config = replace(cached_config, temperature_unit=None)

    async def get_config() -> object:
        if config_read_started.is_set():
            return cached_config
        config_read_started.set()
        await release_config_read.wait()
        return stale_config

    mock_v1_airgradient_client.get_config.side_effect = get_config

    refresh = hass.async_create_task(coordinator.async_refresh())
    await config_read_started.wait()
    write = hass.async_create_task(
        coordinator.async_execute_config_write(asyncio.sleep(0))
    )
    await asyncio.sleep(0)
    release_config_read.set()

    await refresh

    assert coordinator.data.config == cached_config

    await write
    mock_config_apply_delay.assert_awaited_once_with(V1_CONFIG_APPLY_DELAY)


async def test_new_firmware_version(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.sw_version == "3.1.1"
    mock_airgradient_client.get_current_measures.return_value.firmware_version = "3.1.2"
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.sw_version == "3.1.2"


async def test_setup_retry(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test retrying setup."""
    mock_airgradient_client.get_current_measures.side_effect = AirGradientError()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_serial_mismatch(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the configured host serves another device."""
    mock_airgradient_client.get_current_measures.return_value.serial_number = (
        "84fce612f5b9"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_serial_mismatch_marks_update_failed(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a host serving another device fails the coordinator update."""
    await setup_integration(hass, mock_config_entry)
    config_calls = mock_airgradient_client.get_config.call_count
    mock_airgradient_client.get_current_measures.return_value.serial_number = (
        "84fce612f5b9"
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.last_update_success is False
    assert mock_airgradient_client.get_config.call_count == config_calls

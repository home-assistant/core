"""Tests for the homewizard energy component."""
from asyncio import TimeoutError
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohwenergy import AiohwenergyException, DisabledError

from homeassistant.components.homewizard_energy.__init__ import (
    HWEnergyDeviceUpdateCoordinator as Coordinator,
)
from homeassistant.components.homewizard_energy.const import (
    DOMAIN,
    MODEL_KWH_1,
    MODEL_KWH_3,
    MODEL_P1,
    MODEL_SOCKET,
)
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


def get_mock_device(
    serial="aabbccddeeff",
    host="1.2.3.4",
    product_name="P1 meter",
    product_type="HWE-P1",
):
    """Return a mock bridge."""
    mock_device = AsyncMock()
    mock_device._host = host

    mock_device.device.product_name = product_name
    mock_device.device.product_type = product_type
    mock_device.device.serial = serial
    mock_device.device.api_version = "v1"
    mock_device.device.firmware_version = "1.00"

    mock_device.initialize = AsyncMock()
    mock_device.close = AsyncMock()

    return mock_device


async def test_load_unload(aioclient_mock, hass):
    """Test loading and unloading of integration."""

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_failed_host_unavailable(aioclient_mock, hass):
    """Test setup handles unreachable host."""

    def MockInitialize():
        raise TimeoutError()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_detect_api_disabled(aioclient_mock, hass):
    """Test setup detects disabled API."""

    def MockInitialize():
        raise DisabledError()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_handles_aiohwenergy_exception(aioclient_mock, hass):
    """Test setup handles exception from API."""

    def MockInitialize():
        raise AiohwenergyException()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR


async def test_load_handles_generic_exception(aioclient_mock, hass):
    """Test setup handles global exception."""

    def MockInitialize():
        raise Exception()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR


async def test_load_handles_initialization_error(aioclient_mock, hass):
    """Test handles non-exception error."""

    device = get_mock_device()
    device.device = None

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"unique_id": "HWE-P1_aabbccddeeff"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR


async def test_coordinator_calculates_update_interval(aioclient_mock, hass):
    """Test coordinator calculates correct update interval."""

    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 50

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=1)

    # KWH 1 phase
    meter = get_mock_device(product_type=MODEL_KWH_1)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # KWH 3 phase
    meter = get_mock_device(product_type=MODEL_KWH_3)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Socket
    meter = get_mock_device(product_type=MODEL_SOCKET)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Missing config data
    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data = None

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Not an 5.0 meter config data
    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 40

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

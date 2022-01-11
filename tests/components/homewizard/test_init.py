"""Tests for the homewizard component."""
from asyncio import TimeoutError
from datetime import timedelta
from unittest.mock import patch

from aiohwenergy import AiohwenergyException, DisabledError
from pytest import raises

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.update_coordinator import UpdateFailed

from .generator import get_mock_device

from tests.common import MockConfigEntry


async def test_load_unload(aioclient_mock, hass):
    """Test loading and unloading of integration."""

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_handles_aiohwenergy_exception(aioclient_mock, hass):
    """Test setup handles exception from API."""

    def MockInitialize():
        raise AiohwenergyException()

    device = get_mock_device()
    device.initialize.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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


async def test_coordinator_sets_update_interval(aioclient_mock, hass):
    """Test coordinator calculates correct update interval."""

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ].update_interval == timedelta(seconds=5)


async def test_coordinator_failed_to_update(aioclient_mock, hass):
    """Test coordinator handles failed update correctly."""

    # Update failed by internal error
    async def _failed_update() -> bool:
        return False

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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

    device.update = _failed_update

    with raises(UpdateFailed):
        await hass.data[DOMAIN][entry.entry_id]["coordinator"]._async_update_data()


async def test_coordinator_catches_disabled_api(aioclient_mock, hass):
    """Test coordinator handles failed update correctly."""

    # Update failed by internal error
    async def _failed_update() -> bool:
        raise DisabledError()

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
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

    device.update = _failed_update

    with raises(UpdateFailed):
        await hass.data[DOMAIN][entry.entry_id]["coordinator"]._async_update_data()

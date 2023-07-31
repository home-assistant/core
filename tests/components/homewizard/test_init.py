"""Tests for the homewizard component."""
from asyncio import TimeoutError
from unittest.mock import patch

from homewizard_energy.errors import DisabledError, HomeWizardEnergyException

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .generator import get_mock_device

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test loading and unloading of integration."""

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_load_failed_host_unavailable(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test setup handles unreachable host."""

    def MockInitialize():
        raise TimeoutError()

    device = get_mock_device()
    device.device.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_detect_api_disabled(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test setup detects disabled API."""

    def MockInitialize():
        raise DisabledError()

    device = get_mock_device()
    device.device.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_load_removes_reauth_flow(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test setup removes reauth flow when API is enabled."""

    device = get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    # Add reauth flow from 'previously' failed init
    entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    # Initialize entry
    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Flow should be removed
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


async def test_load_handles_homewizardenergy_exception(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test setup handles exception from API."""

    def MockInitialize():
        raise HomeWizardEnergyException()

    device = get_mock_device()
    device.device.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR


async def test_load_handles_generic_exception(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
    """Test setup handles global exception."""

    def MockInitialize():
        raise Exception()

    device = get_mock_device()
    device.device.side_effect = MockInitialize

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.1.1.1"},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR


async def test_load_handles_initialization_error(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> None:
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
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY or ConfigEntryState.SETUP_ERROR

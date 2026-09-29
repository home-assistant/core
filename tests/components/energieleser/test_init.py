"""Tests for the energieleser integration setup and unload."""

import asyncio
from unittest.mock import AsyncMock

from energieleser import (
    DeviceType,
    EnergieleserConnectionError,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
    StromleserOneDevice,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energieleser import FIRMWARE_COORDINATOR
from homeassistant.components.energieleser.const import CONF_SW_VERSION, DOMAIN
from homeassistant.components.energieleser.coordinator import (
    FIRMWARE_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from homeassistant.components.update import ATTR_LATEST_VERSION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .conftest import (
    LATEST_FIRMWARE_VERSIONS,
    STROMLESER_DEVICE_ID,
    STROMLESER_SW_VERSION,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry sets up and unloads cleanly."""
    mock_stromleser_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EnergieleserConnectionError("boom"), id="connection_error"),
        pytest.param(
            EnergieleserUnknownDeviceError("unknown"), id="unknown_device_error"
        ),
        pytest.param(EnergieleserError("generic"), id="generic_error"),
    ],
)
async def test_setup_retries_on_client_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test the entry is retried when the client raises an error during setup."""
    mock_energieleser_client.get_device.side_effect = side_effect
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_device_exposes_discovery_sw_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the firmware version captured at discovery is set on the device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: STROMLESER_DEVICE_ID,
            CONF_SW_VERSION: STROMLESER_SW_VERSION,
        },
        unique_id=STROMLESER_DEVICE_ID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, STROMLESER_DEVICE_ID), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == STROMLESER_SW_VERSION


async def test_meter_locked_repair_issue(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_device: StromleserOneDevice,
    mock_locked_stromleser_device: StromleserOneDevice,
    mock_stromleser_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repair issue is created when meter is locked and deleted when unlocked."""
    mock_energieleser_client.get_device.return_value = mock_locked_stromleser_device
    mock_stromleser_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"pin_locked_{mock_stromleser_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "meter_locked"
    assert (
        issue.learn_more_url
        == "https://docs.energieleser.de/en/docs/stromleser-one/installation/preparation"
    )
    assert issue.translation_placeholders == {
        "device_name": mock_stromleser_config_entry.title,
    }

    mock_energieleser_client.get_device.return_value = mock_stromleser_device
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_meter_locked_repair_issue_removed_on_unload(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_locked_stromleser_device: StromleserOneDevice,
    mock_stromleser_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is deleted when entry is unloaded."""
    mock_energieleser_client.get_device.return_value = mock_locked_stromleser_device
    mock_stromleser_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"pin_locked_{mock_stromleser_config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_unload(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_firmware_coordinator_shared_across_entries(
    hass: HomeAssistant,
    mock_latest_firmware_versions: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
    mock_gasleser_config_entry: MockConfigEntry,
) -> None:
    """Test one firmware API call serves every config entry."""
    mock_stromleser_config_entry.add_to_hass(hass)
    mock_gasleser_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED
    assert mock_gasleser_config_entry.state is ConfigEntryState.LOADED
    assert mock_latest_firmware_versions.call_count == 1
    assert hass.data[FIRMWARE_COORDINATOR].data == LATEST_FIRMWARE_VERSIONS


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_firmware_coordinator_survives_until_last_entry_unloads(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_latest_firmware_versions: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
    mock_gasleser_config_entry: MockConfigEntry,
) -> None:
    """Test remaining entities keep updating and the last unload tears the coordinator down."""
    mock_stromleser_config_entry.add_to_hass(hass)
    mock_gasleser_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_latest_firmware_versions.return_value = {
        **LATEST_FIRMWARE_VERSIONS,
        DeviceType.STROMLESER: "v1.4.31",
    }
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, f"{mock_gasleser_config_entry.unique_id}_firmware"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_LATEST_VERSION] == "v1.4.31"
    assert mock_latest_firmware_versions.call_count == 2

    await hass.config_entries.async_unload(mock_gasleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert FIRMWARE_COORDINATOR not in hass.data


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_setup_does_not_wait_for_firmware_api(
    hass: HomeAssistant,
    mock_latest_firmware_versions: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test a slow firmware API does not delay device setup."""
    release = asyncio.Event()

    async def _slow(*_: object) -> dict[DeviceType, str]:
        await release.wait()
        return dict(LATEST_FIRMWARE_VERSIONS)

    mock_latest_firmware_versions.side_effect = _slow
    mock_stromleser_config_entry.add_to_hass(hass)

    async with asyncio.timeout(1):
        await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.data[FIRMWARE_COORDINATOR].data == LATEST_FIRMWARE_VERSIONS


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_firmware_api_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_latest_firmware_versions: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the entry loads even when the firmware API is down."""
    mock_latest_firmware_versions.side_effect = EnergieleserConnectionError("down")
    mock_stromleser_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED
    assert hass.data[FIRMWARE_COORDINATOR].last_update_success is False

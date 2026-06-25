"""Tests for the homewizard component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch
import weakref

from freezegun.api import FrozenDateTimeFactory
from homewizard_energy.errors import DisabledError, UnauthorizedError
import pytest

from homeassistant.components.homewizard import get_main_device
from homeassistant.components.homewizard.const import (
    DOMAIN,
    battery_mode_cloud_issue_id,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_v1(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test loading and unloading of integration with v1 config."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    weak_ref = weakref.ref(mock_config_entry.runtime_data)
    assert weak_ref() is not None

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_homewizardenergy.combined.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert weak_ref() is None


@pytest.mark.parametrize(("device_fixture"), ["HWE-P1", "HWE-KWH1"])
async def test_load_unload_v2(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
    mock_homewizardenergy_v2: MagicMock,
) -> None:
    """Test loading and unloading of integration with v2 config."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v2.state is ConfigEntryState.LOADED
    assert len(mock_homewizardenergy_v2.combined.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v2.state is ConfigEntryState.NOT_LOADED


async def test_load_failed_host_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test setup handles unreachable host."""
    mock_homewizardenergy.combined.side_effect = TimeoutError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_detect_api_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test setup detects disabled API."""
    mock_homewizardenergy.combined.side_effect = DisabledError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_enable_api"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_load_detect_invalid_token(
    hass: HomeAssistant,
    mock_config_entry_v2: MockConfigEntry,
    mock_homewizardenergy_v2: MagicMock,
) -> None:
    """Test setup detects invalid token."""
    mock_homewizardenergy_v2.combined.side_effect = UnauthorizedError()
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v2.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm_update_token"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry_v2.entry_id


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_load_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test setup creates repair issue for v2 API upgrade."""
    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)

    issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    )
    assert issue is not None

    # Make sure title placeholder is set correctly
    assert issue.translation_placeholders["title"] == "Device"


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_load_creates_repair_issue_when_name_is_updated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test repair issue for v2 API and title update on name change."""
    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue_id = f"migrate_to_v2_api_{mock_config_entry.entry_id}"

    issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert issue is not None

    # Initial title should be "Device"
    assert issue.translation_placeholders["title"] == "Device"

    # Update the device name
    device_registry = dr.async_get(hass)
    device = get_main_device(hass, mock_config_entry)

    # Update device name
    device_registry.async_update_device(
        device_id=device.id,
        name_by_user="My HomeWizard Device",
    )

    # Reload integration to trigger issue update
    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert issue is not None

    # Title should now reflect updated device name
    assert issue.translation_placeholders["title"] == "Device (My HomeWizard Device)"


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_load_removes_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup removes reauth flow when API is enabled."""
    mock_config_entry.add_to_hass(hass)

    # Add reauth flow from 'previously' failed init
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Flow should be removed
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_disablederror_reloads_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test DisabledError reloads integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Make sure current state is loaded and not reauth flow is active
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0

    # Simulate DisabledError and wait for next update
    mock_homewizardenergy.combined.side_effect = DisabledError()

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # State should be setup retry and reauth flow should be active
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_enable_api"
    assert flow.get("handler") == DOMAIN


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_battery_cloud_issue_updates_only_on_state_transition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test battery/cloud issue is only created/deleted when condition changes."""
    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.system.cloud_enabled = False
    combined_data.batteries.mode = "predictive"
    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    issue_events: list[str] = []

    @callback
    def _capture_issue_event(event: Event[ir.EventIssueRegistryUpdatedData]) -> None:
        if event.data["domain"] == DOMAIN and event.data["issue_id"] == issue_id:
            issue_events.append(event.data["action"])

    hass.bus.async_listen(ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED, _capture_issue_event)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_events == ["create"]

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issue_events == ["create"]

    combined_data.system.cloud_enabled = True
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issue_events == ["create", "remove"]

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issue_events == ["create", "remove"]


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_battery_cloud_issue_stale_issue_cleared_on_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test stale battery/cloud issue is removed after reload when resolved."""
    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.batteries.mode = "predictive"
    combined_data.system.cloud_enabled = False
    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    combined_data.system.cloud_enabled = True
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

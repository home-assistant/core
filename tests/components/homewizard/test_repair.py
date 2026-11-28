"""Test the homewizard config flow."""

import asyncio
from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.homewizard.const import (
    DOMAIN,
    UPDATE_INTERVAL,
    battery_mode_cloud_issue_id,
)
from homeassistant.components.homewizard.repairs import async_create_fix_flow
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def _async_get_repair_step(client: TestClient, flow_id: str) -> dict[str, Any]:
    """Fetch the current step without submitting, as the frontend does."""
    resp = await client.get(f"/api/repairs/issues/fix/{flow_id}")
    assert resp.status == HTTPStatus.OK
    return await resp.json()


@pytest.fixture
def fast_token_polling() -> Generator[None]:
    """Do not wait between token requests."""
    with patch(
        "homeassistant.components.homewizard.config_flow.TOKEN_POLL_INTERVAL", 0
    ):
        yield


@pytest.mark.usefixtures("fast_token_polling")
async def test_repair_acquires_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair flow waits for the button press and uses the token."""

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="HWE-BAT_5c2fafabcdef"
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    issue_id = f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None

    assert issue.data.get("entry_id") == mock_config_entry.entry_id

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm_identify"

    # Device is briefly unreachable, then the button is pressed
    mock_homewizardenergy_v2.get_token.side_effect = [
        DisabledError,
        RequestError,
        "cool_token",
    ]

    result = await process_repair_fix_flow(client, flow_id)

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "authorize"
    assert result["progress_action"] == "wait_for_button"

    await hass.async_block_till_done()
    result = await _async_get_repair_step(client, flow_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data[CONF_TOKEN] == "cool_token"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("fast_token_polling")
async def test_repair_button_not_pressed_in_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test repair flow lets the user retry when the button is not pressed."""
    client, result = await _async_open_migrate_repair(
        hass, mock_config_entry, hass_client
    )
    flow_id = result["flow_id"]
    mock_homewizardenergy_v2.get_token.side_effect = DisabledError

    with patch("homeassistant.components.homewizard.config_flow.TOKEN_TIMEOUT", 0):
        result = await process_repair_fix_flow(client, flow_id)
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

    result = await _async_get_repair_step(client, flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize_timeout"

    mock_homewizardenergy_v2.get_token.side_effect = [DisabledError, "cool_token"]

    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "authorize"

    await hass.async_block_till_done()
    result = await _async_get_repair_step(client, flow_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data[CONF_TOKEN] == "cool_token"


@pytest.fixture
def fast_identify() -> Generator[None]:
    """Do not wait between identify requests."""
    with patch("homeassistant.components.homewizard.repairs.IDENTIFY_INTERVAL", 0):
        yield


async def _async_open_migrate_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> tuple[TestClient, dict[str, Any]]:
    """Set up the entry with v2 support and open its migration repair."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    )
    assert result["type"] == FlowResultType.FORM
    return client, result


@pytest.mark.usefixtures("fast_identify")
@pytest.mark.parametrize(
    ("device_fixture", "identify_side_effect", "identify_calls", "step_id"),
    [
        pytest.param(
            "HWE-SKT-11",
            [None, None, RequestError],
            3,
            "confirm_identify",
            id="repeats_until_error",
        ),
        pytest.param(
            "HWE-SKT-11", DisabledError, 1, "confirm_identify", id="api_disabled"
        ),
        pytest.param(
            "HWE-SKT-11", UnsupportedError, 1, "confirm_identify", id="unsupported"
        ),
        pytest.param("HWE-KWH1", None, 0, "confirm", id="not_supported_by_device"),
    ],
)
async def test_repair_identifies_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
    identify_side_effect: list[type[Exception] | None] | type[Exception] | None,
    identify_calls: int,
    step_id: str,
) -> None:
    """Test the migration repair keeps identifying the device until it fails."""
    mock_homewizardenergy.identify.side_effect = identify_side_effect

    _, result = await _async_open_migrate_repair(hass, mock_config_entry, hass_client)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["step_id"] == step_id
    assert len(mock_homewizardenergy.identify.mock_calls) == identify_calls


@pytest.mark.usefixtures("fast_identify")
async def test_repair_identify_stops_after_duration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the migration repair stops identifying after the maximum duration."""
    with patch("homeassistant.components.homewizard.repairs.IDENTIFY_DURATION", 0):
        await _async_open_migrate_repair(hass, mock_config_entry, hass_client)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_homewizardenergy.identify.mock_calls) == 1


async def _async_count_new_identify_calls(mock_homewizardenergy: MagicMock) -> int:
    """Let the event loop run and return how many identify calls were made."""
    identify_calls = len(mock_homewizardenergy.identify.mock_calls)
    for _ in range(5):
        await asyncio.sleep(0)
    return len(mock_homewizardenergy.identify.mock_calls) - identify_calls


@pytest.mark.usefixtures("fast_identify")
async def test_repair_identify_stops_when_closed_on_confirm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test identifying stops when the user closes the confirm step."""
    client, result = await _async_open_migrate_repair(
        hass, mock_config_entry, hass_client
    )
    assert await _async_count_new_identify_calls(mock_homewizardenergy)

    resp = await client.delete(f"/api/repairs/issues/fix/{result['flow_id']}")
    assert resp.status == HTTPStatus.OK

    assert not await _async_count_new_identify_calls(mock_homewizardenergy)


@pytest.mark.usefixtures("fast_identify", "fast_token_polling")
async def test_repair_identify_continues_until_button_pressed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test identifying continues while waiting and stops once authorized."""
    mock_homewizardenergy_v2.get_token.side_effect = DisabledError
    client, result = await _async_open_migrate_repair(
        hass, mock_config_entry, hass_client
    )
    flow_id = result["flow_id"]

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert await _async_count_new_identify_calls(mock_homewizardenergy)

    mock_homewizardenergy_v2.get_token.side_effect = None
    mock_homewizardenergy_v2.get_token.return_value = "cool_token"
    await hass.async_block_till_done()

    assert not await _async_count_new_identify_calls(mock_homewizardenergy)

    result = await _async_get_repair_step(client, flow_id)
    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("fast_identify", "fast_token_polling")
async def test_repair_identify_stops_when_closed_while_waiting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test identifying stops when the user closes the waiting step."""
    mock_homewizardenergy_v2.get_token.side_effect = DisabledError
    client, result = await _async_open_migrate_repair(
        hass, mock_config_entry, hass_client
    )

    result = await process_repair_fix_flow(client, result["flow_id"])
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert await _async_count_new_identify_calls(mock_homewizardenergy)

    resp = await client.delete(f"/api/repairs/issues/fix/{result['flow_id']}")
    assert resp.status == HTTPStatus.OK

    assert not await _async_count_new_identify_calls(mock_homewizardenergy)


async def test_repair_does_not_identify_unloaded_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the migration repair skips identify when the entry is not loaded."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    result = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    mock_homewizardenergy.identify.assert_not_called()


async def test_repair_created_for_cloud_disabled_predictive_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created for incompatible cloud and battery mode."""
    mock_homewizardenergy.combined.return_value.system.cloud_enabled = False
    mock_homewizardenergy.combined.return_value.batteries.mode = "predictive"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.data.get("entry_id") == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_shown_again_after_restart(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue reloaded inactive after a restart is shown again."""
    mock_homewizardenergy.combined.return_value.system.cloud_enabled = False
    mock_homewizardenergy.combined.return_value.batteries.mode = "predictive"
    mock_config_entry.add_to_hass(hass)
    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "config_entry_id": None,
                    "config_subentry_id": None,
                    "created": "2026-01-01T00:00:00+00:00",
                    "dismissed_version": None,
                    "domain": DOMAIN,
                    "is_persistent": False,
                    "issue_id": issue_id,
                }
            ]
        },
    }
    await issue_registry.async_load()
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert not issue.active

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.active
    assert issue.config_entry_id == mock_config_entry.entry_id


async def test_repair_auto_resolves_when_cloud_is_re_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repair issue is auto-resolved when compatibility is restored."""
    mock_homewizardenergy.combined.return_value.system.cloud_enabled = False
    mock_homewizardenergy.combined.return_value.batteries.mode = "predictive"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_homewizardenergy.combined.return_value.system.cloud_enabled = True
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_confirm_enables_cloud_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirming repair enables cloud connection and resolves issue."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.system.cloud_enabled = False
    combined_data.batteries.mode = "predictive"

    def _set_cloud_enabled(*, cloud_enabled: bool) -> None:
        combined_data.system.cloud_enabled = cloud_enabled

    mock_homewizardenergy.system.side_effect = _set_cloud_enabled

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    mock_homewizardenergy.system.assert_called_with(cloud_enabled=True)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (RequestError, "network_error"),
    ],
)
async def test_repair_confirm_enable_cloud_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    exception: type[Exception],
    expected_error: str,
) -> None:
    """Test confirming repair returns recoverable errors if cloud enable fails."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    combined_data = mock_homewizardenergy.combined.return_value
    combined_data.system.cloud_enabled = False
    combined_data.batteries.mode = "predictive"
    mock_homewizardenergy.system.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = battery_mode_cloud_issue_id(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id, json={})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": expected_error}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_repair_unknown_issue_id_raises(hass: HomeAssistant) -> None:
    """Test unknown repair issue id raises ValueError."""
    with pytest.raises(ValueError, match="unknown repair unknown_issue"):
        await async_create_fix_flow(hass, "unknown_issue", {"entry_id": "entry-id"})


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"entry_id": None},
        {"entry_id": 123},
    ],
)
async def test_repair_invalid_entry_id_returns_confirm_flow(
    hass: HomeAssistant,
    data: dict[str, str | int | float | None] | None,
) -> None:
    """Test invalid repair flow data falls back to confirm flow."""
    flow = await async_create_fix_flow(hass, "any_issue", data)
    assert isinstance(flow, ConfirmRepairFlow)

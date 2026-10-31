"""Tests for per-device Gree enrollment."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.gree.const import CONF_IDENTIFIER, DOMAIN
from homeassistant.components.gree.discovery import (
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import discovery_flow, entity_registry as er

from .common import build_device_mock

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def add_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    source: str = config_entries.SOURCE_USER,
    state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Add an existing device entry without starting a connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        title="User chosen title",
        data=data,
        source=source,
        state=state,
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_shows_candidates(hass: HomeAssistant, device: MagicMock) -> None:
    """Adding an entry shows discovered candidates before opening a connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"
    device().bind.assert_not_awaited()


@pytest.mark.parametrize("onboarded", [True, False])
async def test_discovery_requires_confirmation(
    hass: HomeAssistant,
    device: MagicMock,
    onboarded: bool,
    entity_registry: er.EntityRegistry,
) -> None:
    """Discovery never enrolls or binds an unknown unit without consent."""
    data = device_info_to_data(device().device_info)
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=onboarded,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=data,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {
        "name": data["name"],
        "identifier": data["identifier"],
        "host": data["host"],
    }
    assert not hass.config_entries.async_entries(DOMAIN)
    assert not entity_registry.entities
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == normalize_identifier(data["identifier"])
    assert result["result"].version == 2
    assert result["result"].minor_version == 1
    device().bind.assert_awaited_once_with()
    device().close.assert_called_once_with()


async def test_scan_selects_only_one_device(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Selection binds only its responder and persists the original wire identity."""
    other = build_device_mock("Other unit", "192.0.2.2", "AA:BB:CC:11:22:44")
    discovery.mock_devices = [device(), other]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "pick_device"
    device().bind.assert_not_awaited()
    other.bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: normalize_identifier(other.device_info.mac)}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112244"
    assert result["data"] == device_info_to_data(other.device_info)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert device.call_args.args[0].mac == other.device_info.mac
    assert device.call_args.args[0].ip == other.device_info.ip
    assert device.call_args.args[0].port == other.device_info.port
    other.bind.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        pytest.param(None, "no_devices_found", id="empty"),
        pytest.param(OSError, "cannot_connect", id="network-error"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
    ],
)
async def test_scan_empty_or_error(
    hass: HomeAssistant, failure: type[Exception] | None, reason: str
) -> None:
    """A failed scan is distinct from a successful empty LAN scan."""
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery"
    ) as scanner:
        scanner.return_value.async_scan = AsyncMock(
            return_value={}, side_effect=failure
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_scan_filters_configured_identities(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Scanning offers unconfigured responders without affecting known units."""
    known = add_entry(hass, device_info_to_data(device().device_info))
    other = build_device_mock("Other", "192.0.2.2", "aabbcc112244")
    discovery.mock_devices = [device(), other]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "pick_device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: other.device_info.mac}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == other.device_info.mac
    assert hass.config_entries.async_get_entry(known.entry_id) is known
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_all_candidates_configured(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
) -> None:
    """No selection form is shown when every discovered identity is configured."""
    other = build_device_mock("Other", "192.0.2.2", "aabbcc112244")
    discovery.mock_devices = [device(), other]
    add_entry(hass, device_info_to_data(device().device_info))
    add_entry(hass, device_info_to_data(other.device_info))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    device().bind.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        pytest.param(DeviceNotBoundError, "cannot_connect", id="not-bound"),
        pytest.param(DeviceTimeoutError, "cannot_connect", id="device-timeout"),
        pytest.param(OSError, "cannot_connect", id="network-error"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(RuntimeError, "unknown", id="unexpected"),
    ],
)
@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_selected_validation_failure(
    hass: HomeAssistant,
    device: MagicMock,
    failure: type[Exception],
    error: str,
    step: str,
) -> None:
    """Connection errors preserve the active form and always close validation."""
    data = device_info_to_data(device().device_info)
    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=failure,
    ):
        result = await start_selected_step(hass, step, data)
        submission = {
            "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            "discovery_confirm": {},
        }[step]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submission
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)
    device().close.assert_called_once_with()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], submission
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112233"
    assert result["data"] == data
    device().bind.assert_awaited_once_with()
    assert device().close.call_count == 2


async def start_selected_step(
    hass: HomeAssistant, step: str, data: dict[str, Any]
) -> config_entries.ConfigFlowResult:
    """Reach a selected-device form through the public flow manager."""
    if step == "discovery_confirm":
        return await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=data,
        )
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_validation_cancelled(
    hass: HomeAssistant, device: MagicMock, step: str
) -> None:
    """Cancellation propagates rather than becoming a connection error form."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    submission = {
        "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
        "discovery_confirm": {},
    }[step]
    with (
        patch(
            "homeassistant.components.gree.config_flow.async_bind_device",
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await hass.config_entries.flow.async_configure(result["flow_id"], submission)
    device().close.assert_called_once_with()
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("state", "reload"),
    [
        (ConfigEntryState.LOADED, True),
        (ConfigEntryState.SETUP_ERROR, True),
        (ConfigEntryState.SETUP_RETRY, True),
        (ConfigEntryState.NOT_LOADED, True),
        (ConfigEntryState.SETUP_IN_PROGRESS, True),
        (ConfigEntryState.MIGRATION_ERROR, False),
        (ConfigEntryState.FAILED_UNLOAD, False),
        (ConfigEntryState.UNLOAD_IN_PROGRESS, False),
    ],
)
@pytest.mark.parametrize("changed", [CONF_HOST, CONF_PORT])
async def test_known_endpoint_update(
    hass: HomeAssistant,
    device: MagicMock,
    state: ConfigEntryState,
    reload: bool,
    changed: str,
) -> None:
    """Changed endpoints persist and reload only states Core can safely recover."""
    data = device_info_to_data(device().device_info)
    stored = {
        **data,
        CONF_IDENTIFIER: "AA:BB:CC:11:22:33",
        "_migration_source_entry_id": "legacy",
    }
    entry = add_entry(hass, stored, state=state)
    observed = {**data, changed: {CONF_HOST: "192.0.2.2", CONF_PORT: 7001}[changed]}
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        assert schedule.call_count == int(reload)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        assert schedule.call_count == int(reload)
    assert result["reason"] == "already_configured"
    assert entry.data == {
        **observed,
        CONF_IDENTIFIER: stored[CONF_IDENTIFIER],
        "_migration_source_entry_id": "legacy",
    }
    assert entry.title == "User chosen title"
    device().bind.assert_not_awaited()


@pytest.mark.parametrize("metadata", [{}, {"name": "New name", "model": "New model"}])
async def test_known_unchanged_endpoint(
    hass: HomeAssistant, device: MagicMock, metadata: dict[str, str]
) -> None:
    """Neither unchanged nor metadata-only observations reload a retrying unit."""
    data = device_info_to_data(device().device_info)
    entry = add_entry(hass, data, state=ConfigEntryState.SETUP_RETRY)
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={**data, **metadata},
        )
    assert result["reason"] == "already_configured"
    assert entry.data == {**data, **metadata}
    schedule.assert_not_called()
    device().bind.assert_not_awaited()


async def test_disabled_entry_endpoint_update(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Discovery saves disabled devices' addresses without enabling or reloading."""
    data = device_info_to_data(device().device_info)
    entry = add_entry(hass, data, disabled_by=ConfigEntryDisabler.USER)
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={**data, CONF_HOST: "192.0.2.2"},
        )
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.2"
    assert entry.disabled_by is ConfigEntryDisabler.USER
    schedule.assert_not_called()
    device().bind.assert_not_awaited()


async def test_background_ignored_entry_untouched(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """An ignored identifier is not bound, updated or offered again."""
    data = device_info_to_data(device().device_info)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        source=config_entries.SOURCE_IGNORE,
        title="Ignored",
        data={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=data,
    )
    assert result["reason"] == "already_configured"
    assert entry.data == {}
    assert entry.title == "Ignored"
    device().bind.assert_not_awaited()


async def test_explicit_selection_replaces_ignore(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Only explicit user selection replaces an ignored entry."""
    data = device_info_to_data(device().device_info)
    ignored = MockConfigEntry(
        domain=DOMAIN,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        source=config_entries.SOURCE_IGNORE,
    )
    ignored.add_to_hass(hass)
    result = await start_selected_step(hass, "pick_device", data)
    assert hass.config_entries.async_get_entry(ignored.entry_id) is ignored
    device().bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112233"
    assert result["result"].source == config_entries.SOURCE_USER
    assert result["result"].data == data
    assert hass.config_entries.async_get_entry(ignored.entry_id) is None
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_background_deduplication(hass: HomeAssistant, device: MagicMock) -> None:
    """Alternate identifier spellings share one discovery confirmation."""
    data = device_info_to_data(device().device_info)
    first = await start_selected_step(hass, "discovery_confirm", data)
    second = await start_selected_step(
        hass, "discovery_confirm", {**data, CONF_IDENTIFIER: "AA-BB-CC-11-22-33"}
    )
    assert first["step_id"] == "discovery_confirm"
    assert second["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    device().bind.assert_not_awaited()


async def test_pending_discovery_endpoint_update(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Rediscovery refreshes one confirmation without binding before consent."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {
        **data,
        CONF_HOST: "192.0.2.2",
        CONF_PORT: 7001,
        CONF_IDENTIFIER: "AA-BB-CC-11-22-33",
        "name": "Updated name",
    }
    duplicate = await start_selected_step(hass, "discovery_confirm", observed)
    assert duplicate["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    device().bind.assert_not_awaited()
    placeholders = {
        "name": observed["name"],
        "identifier": data[CONF_IDENTIFIER],
        "host": observed[CONF_HOST],
    }
    assert (
        hass.config_entries.flow.async_get(pending["flow_id"])["context"][
            "title_placeholders"
        ]
        == placeholders
    )
    refreshed = await hass.config_entries.flow.async_configure(pending["flow_id"])
    assert refreshed["step_id"] == "discovery_confirm"
    assert refreshed["description_placeholders"] == placeholders
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**observed, CONF_IDENTIFIER: data[CONF_IDENTIFIER]}
    assert result["title"] == observed["name"]
    assert result["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]
    assert device.call_args.args[0].mac == data[CONF_IDENTIFIER]
    device().bind.assert_awaited_once_with()
    device().close.assert_called_once_with()


async def test_background_discovery_endpoint_returns_to_original_address(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Background deduplication cannot suppress an address returning to its origin."""
    data = device_info_to_data(device().device_info)
    await hass.async_start()
    for observed in (data, {**data, CONF_HOST: "192.0.2.2"}, data):
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    pending = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(pending) == 1
    device().bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(pending[0]["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert device.call_args.args[0].ip == data[CONF_HOST]


async def test_pending_discovery_failure_endpoint_update(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A failed confirmation retries the new endpoint rather than the old one."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    device().bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert failed["errors"] == {"base": "cannot_connect"}
    assert device.call_args.args[0].ip == data[CONF_HOST]
    device().bind.reset_mock()
    observed = {**data, CONF_HOST: "192.0.2.2", CONF_PORT: 7001}
    duplicate = await start_selected_step(hass, "discovery_confirm", observed)
    assert duplicate["reason"] == "already_in_progress"
    device().bind.assert_not_awaited()
    device().bind.side_effect = None

    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == observed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]


@pytest.mark.parametrize("failure", [None, DeviceTimeoutError])
async def test_pending_discovery_update_during_validation(
    hass: HomeAssistant, device: MagicMock, failure: type[Exception] | None
) -> None:
    """An in-flight snapshot cannot enroll or restore an obsolete endpoint."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {**data, CONF_HOST: "192.0.2.2", CONF_PORT: 7001}
    binding = asyncio.Event()
    release = asyncio.Event()
    outcome = AsyncMock(side_effect=failure)

    async def bind_snapshot(*args: object) -> None:
        binding.set()
        await release.wait()
        await outcome()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=bind_snapshot,
    ) as bind:
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(pending["flow_id"], {})
        )
        await binding.wait()
        snapshot = device.call_args.args[0]
        duplicate = await start_selected_step(hass, "discovery_confirm", observed)
        assert duplicate["reason"] == "already_in_progress"
        assert snapshot.ip == data[CONF_HOST]
        assert snapshot.port == data[CONF_PORT]
        bind.assert_awaited_once()
        release.set()
        result = await task

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"]["host"] == observed[CONF_HOST]
    assert not hass.config_entries.async_entries(DOMAIN)
    device().bind.assert_not_awaited()
    refreshed = await hass.config_entries.flow.async_configure(pending["flow_id"])
    assert refreshed["description_placeholders"]["host"] == observed[CONF_HOST]
    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == observed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]
    device().bind.assert_awaited_once_with()
    assert device().close.call_count == 2


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param({}, id="unchanged"),
        pytest.param({"name": "Updated name", "model": "Updated model"}, id="metadata"),
        pytest.param({CONF_IDENTIFIER: "AA-BB-CC-11-22-33"}, id="identifier-spelling"),
    ],
)
async def test_pending_discovery_metadata_during_validation(
    hass: HomeAssistant, device: MagicMock, metadata: dict[str, str]
) -> None:
    """Rediscovery at the same endpoint does not invalidate an in-flight bind."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {**data, **metadata}
    binding = asyncio.Event()
    release = asyncio.Event()

    async def bind_snapshot(*args: object) -> None:
        binding.set()
        await release.wait()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=bind_snapshot,
    ) as bind:
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(pending["flow_id"], {})
        )
        await binding.wait()
        snapshot = device.call_args.args[0]
        duplicate = await start_selected_step(hass, "discovery_confirm", observed)
        assert duplicate["reason"] == "already_in_progress"
        assert snapshot.name == data["name"]
        assert snapshot.mac == data[CONF_IDENTIFIER]
        bind.assert_awaited_once()
        release.set()
        result = await task

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**observed, CONF_IDENTIFIER: data[CONF_IDENTIFIER]}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    device().close.assert_called_once_with()


async def test_user_can_enroll_pending_background_candidate(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A pending discovery card cannot block explicit selection."""
    data = device_info_to_data(device().device_info)
    background = await start_selected_step(hass, "discovery_confirm", data)
    user = await start_selected_step(hass, "pick_device", data)
    user = await hass.config_entries.flow.async_configure(
        user["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert user["type"] is FlowResultType.CREATE_ENTRY
    assert user["result"].unique_id == "aabbcc112233"
    assert background["flow_id"] not in {
        flow["flow_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    device().bind.assert_awaited_once_with()


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_entry_created_during_validation(
    hass: HomeAssistant, device: MagicMock, step: str
) -> None:
    """Another winning flow is never replaced after the network await."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    winners: list[MockConfigEntry] = []

    async def another_flow_wins(*args: object) -> None:
        winners.append(add_entry(hass, {**data, CONF_HOST: "192.0.2.99"}))

    with (
        patch(
            "homeassistant.components.gree.config_flow.async_bind_device",
            side_effect=another_flow_wins,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as schedule,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "pick_device": {
                    CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])
                },
                "discovery_confirm": {},
            }[step],
        )
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == winners
    assert winners[0].data[CONF_HOST] == "192.0.2.99"
    schedule.assert_not_called()
    device().close.assert_called_once_with()


@pytest.mark.parametrize(
    ("step", "reason"),
    [
        pytest.param("pick_device", "no_devices_found", id="selection"),
        pytest.param("discovery_confirm", "already_configured", id="discovery"),
    ],
)
async def test_disabled_legacy_identity_reserved(
    hass: HomeAssistant,
    device: MagicMock,
    entity_registry: er.EntityRegistry,
    step: str,
    reason: str,
) -> None:
    """Disabled legacy ownership blocks enrollment without an online migration."""
    data = device_info_to_data(device().device_info)
    legacy = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="gree",
        disabled_by=ConfigEntryDisabler.USER,
    )
    legacy.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "AA:BB:CC:11:22:33",
        config_entry=legacy,
    )
    result = await start_selected_step(hass, step, data)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert hass.config_entries.async_entries(DOMAIN) == [legacy]
    assert legacy.version == 1
    assert legacy.disabled_by is ConfigEntryDisabler.USER
    device().bind.assert_not_awaited()


async def test_pick_device_rejects_unoffered_identity(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """The selector accepts only identities in the server-side scan results."""
    result = await start_selected_step(
        hass, "pick_device", device_info_to_data(device().device_info)
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "not-a-discovered-device"}
        )
    device().bind.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_candidate_configured_before_submission(
    hass: HomeAssistant, device: MagicMock, step: str
) -> None:
    """A candidate enrolled after the form appears is not bound or replaced."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    entry = add_entry(hass, {**data, CONF_HOST: "192.0.2.99"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            "discovery_confirm": {},
        }[step],
    )
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data[CONF_HOST] == "192.0.2.99"
    device().bind.assert_not_awaited()


async def test_known_entry_precedes_pending_flow_check(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A pending confirmation cannot prevent endpoint repair for a known unit."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    entry = add_entry(hass, {**data, CONF_HOST: "192.0.2.99"})
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await start_selected_step(hass, "discovery_confirm", data)
    assert result["reason"] == "already_configured"
    assert entry.data == data
    schedule.assert_called_once_with(entry.entry_id)
    assert (
        hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]["flow_id"]
        == pending["flow_id"]
    )
    device().bind.assert_not_awaited()


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_legacy_reservation_appears_before_submission(
    hass: HomeAssistant,
    device: MagicMock,
    step: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ownership acquired after offering a device blocks binding on submission."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    legacy = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="gree",
        disabled_by=ConfigEntryDisabler.USER,
    )
    legacy.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "climate", DOMAIN, data[CONF_IDENTIFIER], config_entry=legacy
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            "discovery_confirm": {},
        }[step],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [legacy]
    assert (
        entity_registry.async_get(entity.entity_id).config_entry_id == legacy.entry_id
    )
    assert legacy.version == 1
    assert legacy.disabled_by is ConfigEntryDisabler.USER
    device().bind.assert_not_awaited()


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_legacy_reservation_appears_during_validation(
    hass: HomeAssistant,
    device: MagicMock,
    step: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """An identity reserved during binding cannot become a competing entry."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    legacy = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="gree",
        disabled_by=ConfigEntryDisabler.USER,
    )

    async def reserve_identity(*args: object) -> None:
        legacy.add_to_hass(hass)
        entity_registry.async_get_or_create(
            "climate", DOMAIN, data[CONF_IDENTIFIER], config_entry=legacy
        )

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=reserve_identity,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "pick_device": {
                    CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])
                },
                "discovery_confirm": {},
            }[step],
        )
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [legacy]
    device().close.assert_called_once_with()


async def test_scan_cancellation_propagates(hass: HomeAssistant) -> None:
    """A cancelled scan does not become an empty-LAN or connection error."""
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery"
    ) as scanner:
        scanner.return_value.async_scan = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_concurrent_user_and_discovery_validation(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Two consenting flows racing through binding leave exactly one entry."""
    data = device_info_to_data(device().device_info)
    background = await start_selected_step(hass, "discovery_confirm", data)
    user = await start_selected_step(hass, "pick_device", data)
    background_bound = asyncio.Event()
    user_bound = asyncio.Event()
    release_background = asyncio.Event()
    release_user = asyncio.Event()

    async def background_bind(*args: object) -> None:
        background_bound.set()
        await release_background.wait()

    async def user_bind(*args: object) -> None:
        user_bound.set()
        await release_user.wait()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=background_bind,
    ) as bind:
        background_task = hass.async_create_task(
            hass.config_entries.flow.async_configure(background["flow_id"], {})
        )
        await background_bound.wait()
        bind.side_effect = user_bind
        user_task = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                user["flow_id"],
                {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            )
        )
        await user_bound.wait()
        release_user.set()
        user_result = await user_task
        release_background.set()
        background_result = await background_task
    assert user_result["type"] is FlowResultType.CREATE_ENTRY
    assert user_result["result"].unique_id == "aabbcc112233"
    assert background_result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [user_result["result"]]
    assert user_result["result"].data == data
    assert device().close.call_count == 2

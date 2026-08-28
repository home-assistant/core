"""Tests for iZone config flow."""

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.izone import config_flow, discovery as izone_discovery
from homeassistant.components.izone.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import (
    async_finish_user_discover,
    async_follow_user_handoff,
    async_load_yaml_exclude,
    create_mock_controller,
    endpoint_from_controller,
    patch_discovered_controllers,
)

from tests.common import MockConfigEntry


def _make_homekit_info(md: str, host: str | None = None) -> SimpleNamespace:
    """Return a minimal HomeKit discovery info object with attributes."""
    return SimpleNamespace(properties={"md": md}, host=host)


@pytest.fixture(autouse=True)
def mock_izone_timeouts() -> Generator[None]:
    """Mock iZone discovery waits so tests do not sleep for real scan timeouts."""
    with (
        patch(
            "homeassistant.components.izone.discovery.DISCOVERY_IDLE_SECONDS",
            0.04,
        ),
        patch(
            "homeassistant.components.izone.config_flow.USER_SCAN_WAIT_SECONDS",
            0,
        ),
    ):
        yield


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_discovery_success(
    hass: HomeAssistant,
) -> None:
    """Test user Search hands off to the shelf confirm and creates an entry."""
    controller = create_mock_controller("000000001", "192.0.2.55")
    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {CONF_HOST: "192.0.2.55"}
    assert result["result"].unique_id == "000000001"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_discovery_default_selects_first_and_leaves_other(
    hass: HomeAssistant,
) -> None:
    """Default dropdown selection hands off to first UID; other stays on shelf."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers([first, second]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_controller"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {CONF_HOST: "192.0.2.1"}
    assert result["result"].unique_id == "000000001"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    progress = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(progress) == 1
    assert progress[0]["step_id"] == "confirm"
    assert progress[0]["context"]["unique_id"] == "000000002"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_broadcast_skips_already_configured_controller(
    hass: HomeAssistant,
) -> None:
    """Search shelf omits configured controllers and hands off the unconfigured one."""
    configured_controller = create_mock_controller("000000001", "192.0.2.1")
    unconfigured_controller = create_mock_controller("000000002", "192.0.2.2")
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=configured_controller.device_uid,
        data={},
        version=2,
    ).add_to_hass(hass)

    with patch_discovered_controllers([configured_controller, unconfigured_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {CONF_HOST: "192.0.2.2"}
    assert result["result"].unique_id == "000000002"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_discovery_skips_yaml_excluded_controllers(
    hass: HomeAssistant,
) -> None:
    """User Search should not offer controllers excluded by deprecated YAML config."""
    excluded_controller = create_mock_controller("000000001", "192.0.2.1")
    allowed_controller = create_mock_controller("000000002", "192.0.2.2")
    await async_load_yaml_exclude(hass, excluded_controller.device_uid)

    with patch_discovered_controllers([excluded_controller, allowed_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {CONF_HOST: "192.0.2.2"}
    assert result["result"].unique_id == "000000002"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_broadcast_multiple_unconfigured_shows_choice(
    hass: HomeAssistant,
) -> None:
    """Search shows a controller choice when multiple shelf flows are present."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_controller"
        schema_keys = list(result["data_schema"].schema.keys())
        assert len(schema_keys) == 1
        assert str(schema_keys[0].schema) == config_flow.SELECTED_CONTROLLER_UID

        # GET re-show (user_input is None) must not submit the default.
        rerender = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert rerender["type"] is FlowResultType.FORM
        assert rerender["step_id"] == "select_controller"

        # Default is lowest UID; hand off and leave the other on the shelf.
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {CONF_HOST: "192.0.2.2"}
    assert result["result"].unique_id == "000000001"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "000000001"

    progress = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(progress) == 1
    assert progress[0]["step_id"] == "confirm"
    assert progress[0]["context"]["unique_id"] == "000000002"


async def test_select_controller_rerender_hands_off_when_one_left(
    hass: HomeAssistant,
) -> None:
    """Re-show after the shelf shrinks to one candidate hands off that flow."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"

    for progress in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if progress["context"].get("unique_id") == "000000002":
            hass.config_entries.flow.async_abort(progress["flow_id"])

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "continue_setup"
    assert result["next_flow"] is not None


async def test_select_controller_rerender_aborts_when_shelf_empty(
    hass: HomeAssistant,
) -> None:
    """Re-show after every shelf flow is gone aborts no_devices_found."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"

    user_flow_id = result["flow_id"]
    for progress in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if progress["flow_id"] != user_flow_id:
            hass.config_entries.flow.async_abort(progress["flow_id"])

    result = await hass.config_entries.flow.async_configure(user_flow_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_select_controller_hands_off_selected_flow_and_leaves_others(
    hass: HomeAssistant,
) -> None:
    """A selected shelf flow hands off; non-selected shelf flows remain."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.SELECTED_CONTROLLER_UID: "000000002"},
        )
        result = await async_follow_user_handoff(hass, result)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {CONF_HOST: "192.0.2.1"}
    assert result["result"].unique_id == "000000002"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    skipped_flows = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(skipped_flows) == 1
    assert skipped_flows[0]["step_id"] == "confirm"
    assert skipped_flows[0]["context"]["unique_id"] == "000000001"


async def test_select_controller_aborts_when_uid_not_on_shelf(
    hass: HomeAssistant,
) -> None:
    """Abort no_devices_found when the submitted UID is unknown to the shelf."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_select_controller(
        {config_flow.SELECTED_CONTROLLER_UID: "000000099"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("entry_source", "entry_data"),
    [
        pytest.param(
            config_entries.SOURCE_USER,
            {CONF_HOST: "192.0.2.1"},
            id="configured",
        ),
        pytest.param(
            config_entries.SOURCE_IGNORE,
            {},
            id="ignored",
        ),
    ],
)
async def test_select_controller_aborts_already_configured_when_uid_left_shelf(
    hass: HomeAssistant,
    entry_source: str,
    entry_data: dict[str, str],
) -> None:
    """Abort already_configured when the chosen UID was claimed off the shelf."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"

    claimed_uid = "000000001"
    for progress in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if progress["context"].get("unique_id") == claimed_uid:
            hass.config_entries.flow.async_abort(progress["flow_id"])
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=claimed_uid,
        source=entry_source,
        data=entry_data,
        version=2,
    ).add_to_hass(hass)

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_select_controller(
        {config_flow.SELECTED_CONTROLLER_UID: claimed_uid}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_broadcast_aborts_when_all_discovered_are_configured(
    hass: HomeAssistant,
) -> None:
    """Search aborts when every noted controller is already configured."""
    configured_controller = create_mock_controller("000000001", "192.0.2.1")
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=configured_controller.device_uid,
        data={},
        version=2,
    ).add_to_hass(hass)

    with patch_discovered_controllers(configured_controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_aborts_when_all_discovered_are_ignored(
    hass: HomeAssistant,
) -> None:
    """Search aborts when every noted controller is ignored (no shelf flow)."""
    ignored_controller = create_mock_controller("000000001", "192.0.2.1")
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=ignored_controller.device_uid,
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)

    with patch_discovered_controllers(ignored_controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_import_aborts_when_another_izone_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test YAML import does not overlap discovery with an active user flow."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers(controller):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert user_flow["type"] is FlowResultType.SHOW_PROGRESS

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_import_starts_discovery_and_aborts_discovery_started(
    hass: HomeAssistant,
) -> None:
    """YAML import starts shared discovery then aborts so runtime flows take over."""
    with patch(
        "homeassistant.components.izone.discovery.async_ensure_discovery",
        new=AsyncMock(),
    ) as mock_ensure:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    mock_ensure.assert_awaited_once()


async def test_import_aborts_when_discovery_bind_fails(hass: HomeAssistant) -> None:
    """YAML import aborts when discovery cannot bind the UDP socket."""
    with patch(
        "homeassistant.components.izone.discovery.async_ensure_discovery",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


async def test_user_flow_aborts_when_discovery_bind_fails(hass: HomeAssistant) -> None:
    """User flow aborts when discovery cannot bind the UDP socket."""
    with patch(
        "homeassistant.components.izone.discovery.async_scan",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


async def test_user_discover_reshows_progress_while_scan_running(
    hass: HomeAssistant,
) -> None:
    """Re-entering discover while the scan task is pending keeps SHOW_PROGRESS."""
    release = asyncio.Event()

    async def _blocked_scan(_hass: HomeAssistant) -> None:
        await release.wait()

    with patch(
        "homeassistant.components.izone.discovery.async_scan",
        new=AsyncMock(side_effect=_blocked_scan),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "discover"

        still_progress = await hass.config_entries.flow.async_configure(
            result["flow_id"]
        )
        assert still_progress["type"] is FlowResultType.SHOW_PROGRESS
        assert still_progress["progress_action"] == "discover"

        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_search_skips_peer_user_flow_when_building_candidates(
    hass: HomeAssistant,
) -> None:
    """Concurrent SOURCE_USER flows are not treated as shelf candidates."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers(controller):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert first["type"] is FlowResultType.SHOW_PROGRESS
        assert second["type"] is FlowResultType.SHOW_PROGRESS

        first = await async_finish_user_discover(hass, first)

    assert first["type"] is FlowResultType.ABORT
    assert first["reason"] == "continue_setup"
    assert first["next_flow"] is not None
    assert second["flow_id"] in {
        progress["flow_id"]
        for progress in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    }


async def test_user_candidates_skips_discovery_without_host_placeholder(
    hass: HomeAssistant,
) -> None:
    """Discovery flows missing a string host placeholder are not offered."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers([first, second]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    incomplete = {
        "flow_id": "incomplete-discovery",
        "handler": DOMAIN,
        "context": {
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": "000000099",
        },
        "step_id": "confirm",
    }
    progress = list(hass.config_entries.flow.async_progress_by_handler(DOMAIN))
    with patch.object(
        hass.config_entries.flow,
        "async_progress_by_handler",
        return_value=[incomplete, *progress],
    ):
        candidates = flow._async_user_candidates()

    assert {candidate.uid for candidate in candidates} == {"000000001", "000000002"}


@pytest.mark.usefixtures("mock_entry_setup")
async def test_homekit_confirm_uses_discovered_host(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow confirms and uses the discovered controller IP, not the HomeKit host."""
    controller = create_mock_controller(device_ip="192.0.2.3")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["title_placeholders"] == {
            "name": "iZone 000000001",
            "host": "192.0.2.3",
        }
        assert result["description_placeholders"] == {
            "controller_uid": "000000001",
            "host": "192.0.2.3",
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {CONF_HOST: "192.0.2.3"}
    assert result["result"].unique_id == "000000001"


async def test_homekit_fans_out_other_discovered_controllers(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow fans out additional discovered controllers."""
    matched_controller = create_mock_controller("000000001", "192.0.2.3")
    other_controller = create_mock_controller("000000002", "192.0.2.4")

    with patch_discovered_controllers([matched_controller, other_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        await hass.async_block_till_done()

    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(progress) == 2

    current_flow = next(
        flow for flow in progress if flow["flow_id"] == result["flow_id"]
    )
    assert current_flow["context"]["source"] == config_entries.SOURCE_HOMEKIT

    fanout_flow = next(
        flow for flow in progress if flow["flow_id"] != result["flow_id"]
    )
    assert fanout_flow["step_id"] == "confirm"
    assert (
        fanout_flow["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    )
    assert fanout_flow["context"]["unique_id"] == "000000002"


async def test_homekit_flow_sets_device_uid_once(
    hass: HomeAssistant,
) -> None:
    """HomeKit flow sets unique_id to the device UID exactly once (no lock-ID swap)."""
    controller = create_mock_controller("000000001", "192.0.2.3")
    set_unique_id_calls: list[str] = []
    original_set_unique_id = config_flow.IZoneConfigFlow.async_set_unique_id

    async def _recording_set_unique_id(
        self: config_flow.IZoneConfigFlow, uid: str
    ) -> None:
        set_unique_id_calls.append(uid)
        await original_set_unique_id(self, uid)

    with (
        patch_discovered_controllers(controller),
        patch.object(
            config_flow.IZoneConfigFlow,
            "async_set_unique_id",
            _recording_set_unique_id,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert set_unique_id_calls == ["000000001"]


@pytest.mark.usefixtures("mock_entry_setup")
async def test_homekit_aborts_while_user_select_is_open(
    hass: HomeAssistant,
) -> None:
    """HomeKit onboarding for same UID is blocked while user Search select is open."""
    first = create_mock_controller("000000001", "192.0.2.3")
    second = create_mock_controller("000000002", "192.0.2.4")
    with patch_discovered_controllers([first, second]):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        user_flow = await async_finish_user_discover(hass, user_flow)
        assert user_flow["type"] is FlowResultType.FORM
        assert user_flow["step_id"] == "select_controller"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_search_allowed_while_homekit_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """User Search may start while a HomeKit confirm flow is already open."""
    homekit_controller = create_mock_controller("000000001", "192.0.2.3")
    other_controller = create_mock_controller("000000002", "192.0.2.4")
    with patch_discovered_controllers([homekit_controller, other_controller]):
        homekit_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert homekit_flow["type"] is FlowResultType.FORM
        assert homekit_flow["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_controller"


async def test_homekit_aborts_when_uid_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts immediately when the discovered UID is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        ) as mock_discover_all,
        patch(
            "homeassistant.components.izone.discovery.async_discover_endpoint",
        ) as mock_discover_one,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_discover_all.assert_not_called()
    mock_discover_one.assert_not_called()


async def test_homekit_aborts_when_uid_configured_during_discovery(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts if the discovered UID gets configured mid-resolution."""
    controller = create_mock_controller("000000001", "192.0.2.3")

    async def _discover_with_midflight_config(
        hass: HomeAssistant,
    ) -> dict[str, object]:
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="000000001",
            data={},
            version=2,
        ).add_to_hass(hass)
        return {controller.device_uid: endpoint_from_controller(controller)}

    with patch(
        "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        new=AsyncMock(side_effect=_discover_with_midflight_config),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("controllers", "homekit_md", "homekit_host"),
    [
        pytest.param([], "iZone 000000001", "192.0.2.3", id="empty_discovery"),
        pytest.param(
            [create_mock_controller("000000003", "192.0.2.33")],
            "iZone 000000001",
            None,
            id="uid_missing_from_discovery",
        ),
        pytest.param(
            [create_mock_controller("000000002", "192.0.2.44")],
            "iZone 000000001",
            "203.0.113.1",
            id="different_uid_discovered",
        ),
    ],
)
async def test_homekit_aborts_when_target_uid_not_discovered(
    hass: HomeAssistant,
    controllers: list[Mock],
    homekit_md: str,
    homekit_host: str | None,
) -> None:
    """HomeKit aborts when iZone discovery does not yield the advertised UID."""
    with patch_discovered_controllers(controllers):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info(homekit_md, homekit_host),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_homekit_resolves_uid_via_discover_endpoint(
    hass: HomeAssistant,
) -> None:
    """HomeKit falls back to discover_by_uid when the UID is missing from discover_all."""
    target = create_mock_controller("000000001", "192.0.2.1")
    other = create_mock_controller("000000002", "192.0.2.2")
    target_endpoint = endpoint_from_controller(target)

    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_all_endpoints",
            new=AsyncMock(
                return_value={other.device_uid: endpoint_from_controller(other)}
            ),
        ),
        patch(
            "homeassistant.components.izone.discovery.async_discover_endpoint",
            new=AsyncMock(return_value=target_endpoint),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.0.2.1"}
    assert result["result"].unique_id == "000000001"


async def test_homekit_aborts_when_discovery_bind_fails(hass: HomeAssistant) -> None:
    """HomeKit aborts when discovery cannot bind the UDP socket."""
    with patch(
        "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


async def test_user_flow_aborts_when_no_controllers_found(hass: HomeAssistant) -> None:
    """User flow aborts when broadcast discovery returns no controllers."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_without_model_aborts(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow with a non-iZone model string aborts immediately."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=_make_homekit_info("Other Device", "192.0.2.3"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_integration_discovery_aborts_for_yaml_excluded_uid(
    hass: HomeAssistant,
) -> None:
    """Integration discovery should abort for UIDs excluded in YAML config."""
    await async_load_yaml_exclude(hass, "000000002")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": "000000002",
        },
        data={CONF_HOST: "192.0.2.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_integration_discovery_aborts_for_ignored_uid(
    hass: HomeAssistant,
) -> None:
    """Integration discovery should abort for UIDs that have been ignored."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": "000000002",
        },
        data={CONF_HOST: "192.0.2.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_runtime_integration_discovery_starts_confirm_flow(
    hass: HomeAssistant,
) -> None:
    """When the discovery service sees an unconfigured UID, offer setup."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    ).add_to_hass(hass)
    new_ctrl = create_mock_controller("000000002", "192.0.2.2")

    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(new_ctrl)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(progress) == 1
    assert (
        progress[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    )
    assert progress[0]["step_id"] == "confirm"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_integration_discovery_confirm_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Full path: integration-discovery flow confirmed by the user creates an entry."""
    controller = create_mock_controller("000000002", "192.0.2.2")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
            "unique_id": controller.device_uid,
        },
        data={CONF_HOST: controller.device_ip},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {CONF_HOST: "192.0.2.2"}
    assert result["result"].unique_id == "000000002"


async def test_runtime_integration_discovery_skips_yaml_excluded_uid(
    hass: HomeAssistant,
) -> None:
    """Deprecated YAML exclude suppresses auto discovery flows."""
    await async_load_yaml_exclude(hass, "000000002")
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    ).add_to_hass(hass)
    excluded_ctrl = create_mock_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        izone_discovery.async_note_integration_discovery(
            hass, endpoint_from_controller(excluded_ctrl)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_when_uid_already_configured(
    hass: HomeAssistant,
) -> None:
    """No active flow remains when a config entry already exists for the UID."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        data={},
        version=2,
    ).add_to_hass(hass)
    ctrl = create_mock_controller("000000002", "192.0.2.2")

    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(ctrl)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_runtime_integration_discovery_skips_for_ignored_unique_id(
    hass: HomeAssistant,
) -> None:
    """No active flow remains when the UID matches an ignored entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000002",
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)
    ctrl = create_mock_controller("000000002", "192.0.2.2")

    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(ctrl)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_runtime_integration_discovery_allows_during_user_select_controller_step(
    hass: HomeAssistant,
) -> None:
    """Runtime discovery may add shelf flows while the user is choosing controllers."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    ).add_to_hass(hass)
    first = create_mock_controller("000000002", "192.0.2.2")
    second = create_mock_controller("000000003", "192.0.2.3")
    with patch_discovered_controllers([first, second]):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        user_flow = await async_finish_user_discover(hass, user_flow)
    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "select_controller"

    discovery_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(discovery_flows) == 2

    # Re-noting an existing shelf UID must not stack another flow.
    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(first)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    discovery_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(discovery_flows) == 2
    assert {flow["context"]["unique_id"] for flow in discovery_flows} == {
        first.device_uid,
        second.device_uid,
    }


@pytest.mark.usefixtures("mock_entry_setup")
async def test_runtime_integration_discovery_allows_during_user_confirm(
    hass: HomeAssistant,
) -> None:
    """Runtime discovery may add shelf flows while a shelf confirm step is open."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers(first):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)
        assert result["step_id"] == "confirm"

    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(second)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(progress) == 2
    sources = {flow["context"]["source"] for flow in progress}
    assert sources == {
        config_entries.SOURCE_INTEGRATION_DISCOVERY,
    }


async def test_async_setup_starts_import_flow(hass: HomeAssistant) -> None:
    """Test YAML config triggers an import flow."""
    with (
        patch.object(hass.config_entries.flow, "async_init") as mock_async_init,
        patch.object(
            hass,
            "async_create_task",
            side_effect=lambda target: target.close(),
        ) as mock_create_task,
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"exclude": []}})

    mock_async_init.assert_called_once_with(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    mock_create_task.assert_called_once()


def test_is_matching_returns_false_when_either_flow_has_no_uid() -> None:
    """Flow matching should fail when a stable UID cannot be derived."""
    first = SimpleNamespace(context={}, init_data=None)
    second = SimpleNamespace(context={"unique_id": "000000222"}, init_data=None)

    assert config_flow.IZoneConfigFlow.is_matching(first, second) is False


def test_is_matching_returns_true_for_same_flow_uid() -> None:
    """Flow matching should succeed when both flows resolve to the same UID."""
    first = SimpleNamespace(context={"unique_id": "000000111"}, init_data=None)
    second = SimpleNamespace(context={"unique_id": "000000111"}, init_data=None)

    assert config_flow.IZoneConfigFlow.is_matching(first, second) is True


async def test_confirm_asserts_when_controller_data_is_missing(
    hass: HomeAssistant,
) -> None:
    """Confirm asserts when required controller data is unexpectedly missing."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)

    # Corrupt flow-local state that the public path always sets before confirm.
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._discovered_controller_ip = None
    with pytest.raises(AssertionError):
        await flow.async_step_confirm()


async def test_confirm_asserts_when_unique_id_is_not_string(
    hass: HomeAssistant,
) -> None:
    """Confirm asserts when flow unique_id is unexpectedly not a string."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await async_finish_user_discover(hass, result)
        result = await async_follow_user_handoff(hass, result)

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow.context["unique_id"] = None

    with pytest.raises(AssertionError):
        await flow.async_step_confirm({})


def test_async_fan_out_skips_uids_already_in_progress() -> None:
    """Fan-out skips scheduling flows for UIDs already in progress."""
    candidate = endpoint_from_controller(
        create_mock_controller("000000002", "192.0.2.2")
    )
    # Drive the helper with a stub flow: happy-path fan-out tests only cover the
    # "schedule missing UIDs" branch, not the already-in-progress skip.
    fake_flow = SimpleNamespace(
        _async_current_ids=Mock(return_value=set()),
        _async_in_progress=Mock(return_value=[{"context": {"unique_id": "000000002"}}]),
        _async_schedule_integration_discovery_flow=Mock(),
    )

    config_flow.IZoneConfigFlow._async_fan_out_discovered_endpoints(
        fake_flow,
        [candidate],
        selected_uid="000000001",
    )

    fake_flow._async_schedule_integration_discovery_flow.assert_not_called()


async def test_homekit_aborts_for_yaml_excluded_uid_without_discovery(
    hass: HomeAssistant,
) -> None:
    """HomeKit setup aborts immediately for YAML excluded UIDs."""
    await async_load_yaml_exclude(hass, "000000001")

    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        ) as mock_discover_all,
        patch(
            "homeassistant.components.izone.discovery.async_discover_endpoint",
        ) as mock_discover_one,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    mock_discover_all.assert_not_called()
    mock_discover_one.assert_not_called()


async def test_homekit_aborts_for_ignored_uid(
    hass: HomeAssistant,
) -> None:
    """HomeKit setup aborts for UIDs that have been ignored."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        ) as mock_discover_all,
        patch(
            "homeassistant.components.izone.discovery.async_discover_endpoint",
        ) as mock_discover_one,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_discover_all.assert_not_called()
    mock_discover_one.assert_not_called()


async def test_async_migrate_entry_clears_legacy_data(
    hass: HomeAssistant,
) -> None:
    """v1→v2 migration clears legacy entry data without network I/O.

    ConfigEntryNotReady retry semantics only work inside async_setup_entry — raising
    from async_migrate_entry permanently lands the entry in MIGRATION_ERROR with no
    retry path. Setup then heals unique_id=DOMAIN / missing CONF_HOST via discovery.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={"host": "192.0.2.1"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {}

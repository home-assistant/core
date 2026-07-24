"""Tests for iZone config flow."""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pizone
import pytest

from homeassistant import config_entries
from homeassistant.components.izone import config_flow, discovery as izone_discovery
from homeassistant.components.izone.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import (
    async_load_yaml_exclude,
    create_mock_controller,
    endpoint_from_controller,
    patch_discovered_controllers,
)

from tests.common import MockConfigEntry


def _make_homekit_info(md: str, host: str | None = None) -> SimpleNamespace:
    """Return a minimal HomeKit discovery info object with attributes."""
    return SimpleNamespace(properties={"md": md}, host=host)


def _user_search_input() -> dict[str, str]:
    """Return user-step input that triggers broadcast discovery."""
    return {config_flow.CONF_SETUP_METHOD: config_flow.SETUP_METHOD_SEARCH}


def _user_manual_host_input(host: str) -> dict[str, str]:
    """Return user-step input for manual host entry."""
    return {
        config_flow.CONF_SETUP_METHOD: config_flow.SETUP_METHOD_MANUAL_HOST,
        CONF_HOST: host,
    }


async def _configure_user_search(hass: HomeAssistant, flow_id: str) -> dict[str, Any]:
    """Submit the user step choosing broadcast discovery."""
    return await hass.config_entries.flow.async_configure(flow_id, _user_search_input())


@pytest.fixture(autouse=True)
def mock_izone_timeouts() -> Generator[None]:
    """Mock iZone idle-stop delay to speed up tests."""
    with patch(
        "homeassistant.components.izone.discovery.DISCOVERY_IDLE_SECONDS",
        0.04,
    ):
        yield


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_discovery_success(
    hass: HomeAssistant,
) -> None:
    """Test user flow confirms and creates an entry for a discovered controller."""
    controller = create_mock_controller("000000001", "192.0.2.55")
    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"
        progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert progress[0]["context"].get("confirm_only") is True
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {CONF_HOST: "192.0.2.55"}
    assert result["result"].unique_id == "000000001"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_discovery_default_selects_first_and_queues_other(
    hass: HomeAssistant,
) -> None:
    """Default dropdown selection configures first UID and queues the other for confirm."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers([first, second]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "select_controller"
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
    """Test broadcast discovery skips configured controllers and sets up an unconfigured one."""
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
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"
        progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert progress[0]["context"].get("confirm_only") is True
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
    """User flow should not offer controllers excluded by deprecated YAML config."""
    excluded_controller = create_mock_controller("000000001", "192.0.2.1")
    allowed_controller = create_mock_controller("000000002", "192.0.2.2")
    await async_load_yaml_exclude(hass, excluded_controller.device_uid)

    with patch_discovered_controllers([excluded_controller, allowed_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"
        progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert progress[0]["context"].get("confirm_only") is True
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
    """Test broadcast discovery shows a controller choice when multiple unconfigured controllers are found."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "select_controller"
        schema_keys = list(result["data_schema"].schema.keys())
        assert len(schema_keys) == 1
        assert str(schema_keys[0].schema) == config_flow.SELECTED_CONTROLLER_UID

        # Choose one and queue the other as integration discovery (confirm step).
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


async def test_select_controller_aborts_when_choices_missing(
    hass: HomeAssistant,
) -> None:
    """Controller selection aborts if discovered choices were lost on the flow."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "select_controller"

    # Public configure cannot clear flow-local discovery state; poke the in-progress
    # instance so the empty-choices abort path is exercised.
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._user_discovered_endpoints = None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_select_controller_aborts_when_uid_not_in_choices(
    hass: HomeAssistant,
) -> None:
    """Controller selection aborts if the submitted UID is not in the choices."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "select_controller"

    # Schema validation rejects unknown UIDs; call the step directly with a UID that
    # is not in the discovered set to cover the step's own abort.
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_select_controller(
        {config_flow.SELECTED_CONTROLLER_UID: "000000099"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_select_controller_creates_selected_uid_and_queues_others(
    hass: HomeAssistant,
) -> None:
    """A selected controller is configured and non-selected controllers are queued."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "select_controller"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.SELECTED_CONTROLLER_UID: "000000002"},
        )
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


async def test_broadcast_aborts_when_all_discovered_are_configured(
    hass: HomeAssistant,
) -> None:
    """Test broadcast discovery aborts when every discovered controller is configured."""
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
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_flow_offers_ignored_controller_for_setup(
    hass: HomeAssistant,
) -> None:
    """Ignored controllers appear in the user picker and can be set up again."""
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
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm_ignored"
        progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert progress[0]["context"].get("confirm_only") is True
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "000000001"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_confirm_uses_confirm_only(hass: HomeAssistant) -> None:
    """Confirm step is confirm-only so closing the dialog dismisses silently."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await _configure_user_search(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert progress[0]["context"].get("confirm_only") is True


async def test_import_aborts_when_another_izone_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test YAML import does not overlap discovery with an active user flow."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers(controller):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "user"

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
        "homeassistant.components.izone.discovery.async_discover_all_endpoints",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


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
        assert flow["context"]["title_placeholders"] == {"name": "iZone 000000001"}
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
async def test_homekit_aborts_while_user_confirm_is_open(
    hass: HomeAssistant,
) -> None:
    """HomeKit onboarding for same UID is blocked while a user flow is already active."""
    controller = create_mock_controller("000000001", "192.0.2.3")
    with patch_discovered_controllers(controller):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert user_flow["type"] is FlowResultType.FORM
        assert user_flow["step_id"] == "user"
        user_flow = await _configure_user_search(hass, user_flow["flow_id"])
        assert user_flow["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_flow_continues_when_homekit_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Manual user setup is allowed while a discovered-device flow is open."""
    controller = create_mock_controller("000000001", "192.0.2.3")
    with patch_discovered_controllers(controller):
        homekit_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert homekit_flow["type"] is FlowResultType.FORM
        assert homekit_flow["step_id"] == "confirm"

        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "user"


async def test_user_flow_continues_when_integration_discovery_in_progress(
    hass: HomeAssistant,
) -> None:
    """Manual user setup is allowed while an integration discovery confirm is open."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers(controller):
        discovery_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_INTEGRATION_DISCOVERY,
                "unique_id": "000000001",
            },
            data={CONF_HOST: "192.0.2.1"},
        )
        assert discovery_flow["step_id"] == "confirm"

        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "user"


async def test_new_user_flow_replaces_stale_user_flow(
    hass: HomeAssistant,
) -> None:
    """A fresh user flow replaces an earlier one left open (e.g. after refresh)."""
    with patch(
        "homeassistant.components.izone.discovery.discovery_service_active",
        return_value=False,
    ):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert first["step_id"] == "user"

        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert second["type"] is FlowResultType.FORM
    assert second["step_id"] == "user"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    assert (
        hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]["flow_id"]
        == second["flow_id"]
    )


@pytest.mark.usefixtures("mock_entry_setup")
async def test_new_user_flow_replaces_stale_confirm_after_ignore(
    hass: HomeAssistant,
) -> None:
    """Re-setup after ignore works when an earlier confirm flow was left open."""
    ignored_controller = create_mock_controller("000000001", "192.0.2.1")
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=ignored_controller.device_uid,
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)

    with patch_discovered_controllers(ignored_controller):
        stale = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        stale = await _configure_user_search(hass, stale["flow_id"])
        assert stale["step_id"] == "confirm_ignored"

        replacement = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert replacement["step_id"] == "user"

        replacement = await _configure_user_search(hass, replacement["flow_id"])
        assert replacement["step_id"] == "confirm_ignored"
        result = await hass.config_entries.flow.async_configure(
            replacement["flow_id"], {}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "000000001"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 0


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


async def test_user_flow_returns_to_form_when_no_controllers_found(
    hass: HomeAssistant,
) -> None:
    """User flow loops back to the setup form when broadcast discovery finds nothing."""
    with (
        patch_discovered_controllers([]),
        patch(
            "homeassistant.components.izone.discovery.async_stop_discovery",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_devices_found"}
    # Search must remain available after an empty scan (not host-only).
    assert config_flow.CONF_SETUP_METHOD in result["data_schema"].schema
    mock_stop.assert_awaited_once()


async def test_user_flow_can_search_again_after_empty_discovery(
    hass: HomeAssistant,
) -> None:
    """After an empty search, choosing Search again still runs discovery."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with patch_discovered_controllers([]) as (mock_discover_all, _):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["errors"] == {"base": "no_devices_found"}

        mock_discover_all.side_effect = None
        mock_discover_all.return_value = {
            controller.device_uid: endpoint_from_controller(controller)
        }
        result = await _configure_user_search(hass, result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_manual_host_success(hass: HomeAssistant) -> None:
    """Manual host entry probes the bridge and continues to confirm."""
    controller = create_mock_controller("000000001", "192.0.2.55")
    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_by_host",
            new=AsyncMock(return_value=endpoint_from_controller(controller)),
        ),
        patch(
            "homeassistant.components.izone.discovery.discovery_service_active",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("192.0.2.55")
        )
        assert result["step_id"] == "confirm"
        progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert progress[0]["context"].get("confirm_only") is True
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.0.2.55"}


async def test_user_blank_host_submits_search(hass: HomeAssistant) -> None:
    """Leaving the host blank triggers broadcast discovery."""
    controller = create_mock_controller("000000001", "192.0.2.1")
    with (
        patch_discovered_controllers(controller),
        patch(
            "homeassistant.components.izone.discovery.discovery_service_active",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                config_flow.CONF_SETUP_METHOD: config_flow.SETUP_METHOD_SEARCH,
                CONF_HOST: "",
            },
        )

    assert result["step_id"] == "confirm"


async def test_user_manual_host_required_when_enter_host_selected(
    hass: HomeAssistant,
) -> None:
    """Enter host without an address shows a field error."""
    with patch(
        "homeassistant.components.izone.discovery.discovery_service_active",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("")
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "required"}


async def test_user_manual_host_unreachable(hass: HomeAssistant) -> None:
    """Unreachable manual host returns to the user form with an error."""
    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_by_host",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.izone.discovery.discovery_service_active",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("192.0.2.99")
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_manual_host_already_configured_aborts(hass: HomeAssistant) -> None:
    """Re-entering a host for an existing controller aborts before probing."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000025841",
        data={CONF_HOST: "10.0.0.90"},
        version=2,
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.discovery.async_discover_by_host",
    ) as mock_discover_by_host:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("10.0.0.90")
        )

    mock_discover_by_host.assert_not_called()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_manual_host_claimed_controller_aborts(hass: HomeAssistant) -> None:
    """Claim-cache collision aborts when HA has no matching host entry yet."""
    with patch(
        "homeassistant.components.izone.discovery.async_discover_by_host",
        new=AsyncMock(
            side_effect=pizone.ControllerAlreadyClaimedError(
                "Controller 000025841 already created"
            )
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("10.0.0.90")
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_flow_host_only_when_entry_loaded(hass: HomeAssistant) -> None:
    """When an iZone entry is already loaded, the user step asks for a host only."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert config_flow.CONF_SETUP_METHOD not in result["data_schema"].schema
    assert CONF_HOST in result["data_schema"].schema


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_host_only_empty_host_required(hass: HomeAssistant) -> None:
    """Host-only form requires a non-empty host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "required"}


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_host_only_probes_and_confirms(hass: HomeAssistant) -> None:
    """Host-only form probes the entered address and continues to confirm."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    new_controller = create_mock_controller("000000002", "192.0.2.55")
    with patch(
        "homeassistant.components.izone.discovery.async_discover_by_host",
        new=AsyncMock(return_value=endpoint_from_controller(new_controller)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.55"}
        )

    assert result["step_id"] == "confirm"


@pytest.mark.usefixtures("mock_entry_setup")
async def test_user_host_only_unreachable_keeps_host_defaults(
    hass: HomeAssistant,
) -> None:
    """Host-only cannot_connect redisplays the form with the entered host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.izone.discovery.async_discover_by_host",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.99"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    assert config_flow.CONF_SETUP_METHOD not in result["data_schema"].schema


async def test_user_manual_host_aborts_when_discovery_bind_fails(
    hass: HomeAssistant,
) -> None:
    """Manual host aborts when discovery cannot bind the UDP socket."""
    with patch(
        "homeassistant.components.izone.discovery.async_discover_by_host",
        new=AsyncMock(side_effect=OSError("bind failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("192.0.2.55")
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


async def test_user_manual_host_unpaired_aborts(hass: HomeAssistant) -> None:
    """Unpaired bridge placeholder aborts manual host setup."""
    with (
        patch(
            "homeassistant.components.izone.discovery.async_discover_by_host",
            new=AsyncMock(side_effect=pizone.UnpairedBridgeError("unpaired")),
        ),
        patch(
            "homeassistant.components.izone.discovery.discovery_service_active",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_manual_host_input("192.0.2.111")
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unpaired_bridge"


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


async def test_runtime_integration_discovery_skips_during_user_select_controller_step(
    hass: HomeAssistant,
) -> None:
    """Do not stack auto discovery while the user is choosing discovered controllers."""
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
        assert user_flow["type"] is FlowResultType.FORM
        assert user_flow["step_id"] == "user"
        user_flow = await _configure_user_search(hass, user_flow["flow_id"])
        assert user_flow["step_id"] == "select_controller"

    new_ctrl = create_mock_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        izone_discovery.async_note_integration_discovery(
            hass, endpoint_from_controller(new_ctrl)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


@pytest.mark.usefixtures("mock_entry_setup")
async def test_runtime_integration_discovery_skips_during_user_confirm(
    hass: HomeAssistant,
) -> None:
    """Runtime discovery stays suppressed while an interactive user flow is active."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers(first):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"

    izone_discovery.async_note_integration_discovery(
        hass, endpoint_from_controller(second)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(progress) == 1
    assert progress[0]["context"]["source"] == config_entries.SOURCE_USER


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
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"

    # Corrupt flow-local state that the public path always sets before confirm.
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._discovered_controller_ip = None
    with pytest.raises(AssertionError):
        await flow.async_step_confirm({})


async def test_confirm_asserts_when_unique_id_is_not_string(
    hass: HomeAssistant,
) -> None:
    """Confirm asserts when flow unique_id is unexpectedly not a string."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "user"
        result = await _configure_user_search(hass, result["flow_id"])
        assert result["step_id"] == "confirm"

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

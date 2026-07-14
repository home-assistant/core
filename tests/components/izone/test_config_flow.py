"""Tests for iZone config flow."""

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
    async_install_discovery_service,
    async_load_yaml_exclude,
    create_mock_controller,
    patch_discovered_controllers,
)

from tests.common import MockConfigEntry


def _make_homekit_info(md: str, host: str | None = None) -> SimpleNamespace:
    """Return a minimal HomeKit discovery info object with attributes."""
    return SimpleNamespace(properties={"md": md}, host=host)


@pytest.fixture(autouse=True)
def mock_izone_timeouts() -> Generator[None]:
    """Mock iZone timeout constants to speed up tests."""
    with (
        patch(
            "homeassistant.components.izone.discovery.TIMEOUT_DISCOVERY",
            0.01,
        ),
        patch(
            "homeassistant.components.izone.discovery.DISCOVERY_IDLE_SECONDS",
            0.04,
        ),
    ):
        yield


async def test_user_discovery_success(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test user flow confirms and creates an entry for a discovered controller."""
    controller = create_mock_controller("000000001", "192.0.2.55")
    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}
    assert result["result"].unique_id == "000000001"


async def test_user_discovery_default_selects_first_and_queues_other(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Default dropdown selection configures first UID and queues the other for confirm."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers([first, second]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_controller"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}
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


async def test_broadcast_skips_already_configured_controller(
    hass: HomeAssistant, mock_entry_setup: None
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
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}
    assert result["result"].unique_id == "000000002"


async def test_user_discovery_skips_yaml_excluded_controllers(
    hass: HomeAssistant, mock_entry_setup: None
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
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}
    assert result["result"].unique_id == "000000002"


async def test_broadcast_multiple_unconfigured_shows_choice(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test broadcast discovery shows a controller choice when multiple unconfigured controllers are found."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_controller"
        schema_keys = list(result["data_schema"].schema.keys())
        assert len(schema_keys) == 1
        assert str(schema_keys[0].schema) == config_flow.SELECTED_CONTROLLER_UID

        # Choose one and queue the other as integration discovery (confirm step).
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}
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
    """Test controller selection aborts if the discovered controller choices are missing."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._user_discovered_controllers = None

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_select_controller_aborts_when_uid_not_in_choices(
    hass: HomeAssistant,
) -> None:
    """Test controller selection aborts if a submitted UID is not in the choices."""
    first_controller = create_mock_controller("000000001", "192.0.2.1")
    second_controller = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_select_controller(
        {config_flow.SELECTED_CONTROLLER_UID: "000000099"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_select_controller_creates_selected_uid_and_queues_others(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """A selected controller is configured and non-selected controllers are queued."""
    first_controller = create_mock_controller("000000002", "192.0.2.1")
    second_controller = create_mock_controller("000000001", "192.0.2.2")

    with patch_discovered_controllers([first_controller, second_controller]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.SELECTED_CONTROLLER_UID: "000000002"},
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_aborts_when_all_discovered_are_ignored(
    hass: HomeAssistant,
) -> None:
    """User flow aborts when every discovered controller has been explicitly ignored.

    _async_get_unconfigured_controllers uses include_ignore=True so controllers
    whose entries carry SOURCE_IGNORE are not re-offered as configurable, respecting
    the user's earlier choice to dismiss them.
    """
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reuses_existing_discovery_service(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test config flow reuses the running discovery service without starting a new one."""
    controller = create_mock_controller("000000002", "192.0.2.2")
    await async_install_discovery_service(hass, controller)

    with patch(
        "homeassistant.components.izone.config_flow.pizone.discovery",
    ) as mock_pizone_discovery:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}
    assert result["result"].unique_id == "000000002"
    mock_pizone_discovery.assert_not_called()


async def test_import_starts_discovery_service(
    hass: HomeAssistant,
) -> None:
    """Test YAML import starts discovery so runtime discovery can offer flows."""
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        new=AsyncMock(),
    ) as mock_start:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"
    mock_start.assert_awaited_once_with(hass)


async def test_import_logs_and_aborts_when_discovery_service_cannot_start(
    hass: HomeAssistant,
) -> None:
    """Test YAML import aborts cleanly if discovery startup raises OSError."""
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        new=AsyncMock(side_effect=OSError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


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
    assert user_flow["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_homekit_confirm_uses_discovered_host(
    hass: HomeAssistant, mock_entry_setup: None
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
    assert result["data"] == {}
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


async def test_homekit_aborts_while_user_confirm_is_open(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """HomeKit onboarding for same UID is blocked while a user flow is already active."""
    controller = create_mock_controller("000000001", "192.0.2.3")
    with patch_discovered_controllers(controller):
        user_flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert user_flow["type"] is FlowResultType.FORM
        assert user_flow["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_broadcast_aborts_when_homekit_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test user broadcast discovery aborts when a HomeKit flow is already active."""
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
        result = user_flow

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


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

    with patch(
        "homeassistant.components.izone.discovery.async_discover_controllers",
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_discover_controllers.assert_not_called()


async def test_homekit_aborts_when_uid_configured_during_discovery(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts if the discovered UID gets configured mid-resolution."""
    controller = create_mock_controller("000000001", "192.0.2.3")

    async def _fetch_with_midflight_config(timeout=None):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="000000001",
            data={},
            version=2,
        ).add_to_hass(hass)
        return {controller.device_uid: controller}

    with patch_discovered_controllers(controller) as service:
        service.pi_disco.fetch_controllers = AsyncMock(
            side_effect=_fetch_with_midflight_config
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_homekit_aborts_when_uid_not_found_in_discovery(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts when the discovered UID cannot be found via iZone discovery."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_controller_unavailable_during_discovery_wait(
    hass: HomeAssistant,
) -> None:
    """HomeKit aborts when the advertised UID is not found during iZone discovery."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_aborts_when_no_controllers_found(hass: HomeAssistant) -> None:
    """User flow aborts when broadcast discovery returns no controllers."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()


async def test_user_flow_abort_when_discovery_service_cannot_start(
    hass: HomeAssistant,
) -> None:
    """User flow aborts when discovery startup fails."""
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


async def test_user_discovery_with_shared_service_without_matches_aborts(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """User flow aborts when discovery refresh returns no controllers."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

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


async def test_homekit_without_model_does_not_start_discovery(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow does not trigger iZone discovery for a non-iZone model."""
    with patch(
        "homeassistant.components.izone.discovery.async_discover_controllers",
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("Other Device"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    mock_discover_controllers.assert_not_called()


async def test_homekit_aborts_when_matching_uid_not_discovered(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts when no discovered controller matches model UID."""
    controller = create_mock_controller("000000003", "192.0.2.33")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_nothing_found(hass: HomeAssistant) -> None:
    """Test HomeKit aborts when iZone discovery finds no controllers."""
    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_discovered_uid_missing(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts when discovery returns controllers but not the advertised UID."""
    different_controller = create_mock_controller("000000002", "192.0.2.44")

    with patch_discovered_controllers(different_controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_flow_aborts_at_confirm_when_controller_disappears(
    hass: HomeAssistant,
) -> None:
    """HomeKit confirm aborts when the controller is gone by the time the user confirms."""
    controller = create_mock_controller("000000001", "192.0.2.3")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_discovered_controllers([]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_discovery_startup_fails(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow aborts when discovery service cannot start."""
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


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
        data={"host": "192.0.2.2"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_runtime_integration_discovery_starts_confirm_flow(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """When the discovery service sees an unconfigured UID, offer setup."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="000000001",
        data={},
        version=2,
    ).add_to_hass(hass)
    new_ctrl = create_mock_controller("000000002", "192.0.2.2")

    izone_discovery.async_note_integration_discovery(hass, new_ctrl)
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(progress) == 1
    assert (
        progress[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    )
    assert progress[0]["step_id"] == "confirm"


async def test_integration_discovery_confirm_creates_entry(
    hass: HomeAssistant, mock_entry_setup: None
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

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
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
        izone_discovery.async_note_integration_discovery(hass, excluded_ctrl)
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

    izone_discovery.async_note_integration_discovery(hass, ctrl)
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

    izone_discovery.async_note_integration_discovery(hass, ctrl)
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
    assert user_flow["step_id"] == "select_controller"

    new_ctrl = create_mock_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        izone_discovery.async_note_integration_discovery(hass, new_ctrl)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_during_user_confirm(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Runtime discovery stays suppressed while an interactive user flow is active."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    with patch_discovered_controllers(first):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "confirm"

    izone_discovery.async_note_integration_discovery(hass, second)
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


def test_flow_uid_for_matching_returns_none_when_no_uid() -> None:
    """Flow UID extraction returns None when context has no unique_id."""
    flow = SimpleNamespace(context={}, init_data=None)

    assert config_flow._flow_uid_for_matching(flow) is None


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


async def test_homekit_aborts_for_yaml_excluded_uid_without_discovery(
    hass: HomeAssistant,
) -> None:
    """HomeKit setup aborts immediately for YAML excluded UIDs."""
    await async_load_yaml_exclude(hass, "000000001")

    with patch(
        "homeassistant.components.izone.discovery.async_discover_controllers"
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    mock_discover_controllers.assert_not_called()


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

    with patch(
        "homeassistant.components.izone.discovery.async_discover_controllers"
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_discover_controllers.assert_not_called()


async def test_confirm_asserts_when_controller_data_is_missing(
    hass: HomeAssistant,
) -> None:
    """Confirm asserts when required controller data is unexpectedly missing."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow._discovered_controller_ip = None
    with pytest.raises(AssertionError):
        await flow.async_step_confirm()


async def test_confirm_aborts_when_refresh_discovers_no_controllers(
    hass: HomeAssistant,
) -> None:
    """Confirm aborts when a follow-up discovery refresh returns no controllers."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]

    with patch_discovered_controllers([]):
        result = await flow.async_step_confirm({})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_confirm_asserts_when_unique_id_is_not_string(
    hass: HomeAssistant,
) -> None:
    """Confirm asserts when flow unique_id is unexpectedly not a string."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow.context["unique_id"] = None

    with (
        patch_discovered_controllers(controller),
        pytest.raises(AssertionError),
    ):
        await flow.async_step_confirm({})


async def test_confirm_aborts_when_unique_id_controller_not_found(
    hass: HomeAssistant,
) -> None:
    """Confirm aborts when the flow UID is not returned by discovery."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]
    flow.context["unique_id"] = "000009999"

    with patch_discovered_controllers(controller):
        result = await flow.async_step_confirm({})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_confirm_aborts_when_discovery_startup_fails(
    hass: HomeAssistant,
) -> None:
    """Test confirm step aborts when discovery service cannot start."""
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    flow = hass.config_entries.flow._progress[result["flow_id"]]

    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        side_effect=OSError,
    ):
        result = await flow.async_step_confirm({})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_failed"


def test_filter_yaml_exclude_returns_original_when_no_exclusions(
    hass: HomeAssistant,
) -> None:
    """YAML exclusion helper returns unchanged mapping when no excludes are present."""
    controllers = {"000000001": create_mock_controller("000000001", "192.0.2.1")}

    assert (
        config_flow.IZoneConfigFlow._filter_yaml_exclude(hass, controllers)
        is controllers
    )


async def test_filter_yaml_exclude_removes_excluded_controllers(
    hass: HomeAssistant,
) -> None:
    """YAML exclusion helper removes matching UIDs from discovered controllers."""
    first = create_mock_controller("000000001", "192.0.2.1")
    second = create_mock_controller("000000002", "192.0.2.2")
    await async_load_yaml_exclude(hass, "000000002")

    filtered = config_flow.IZoneConfigFlow._filter_yaml_exclude(
        hass,
        {first.device_uid: first, second.device_uid: second},
    )

    assert filtered == {first.device_uid: first}


def test_async_fan_out_skips_uids_already_in_progress() -> None:
    """Fan-out should skip scheduling flows for UIDs already in progress."""
    candidate = create_mock_controller("000000002", "192.0.2.2")
    fake_flow = SimpleNamespace(
        _async_current_ids=Mock(return_value=set()),
        _async_in_progress=Mock(return_value=[{"context": {"unique_id": "000000002"}}]),
        _async_schedule_integration_discovery_flow=Mock(),
    )

    config_flow.IZoneConfigFlow._async_fan_out_discovered_controllers(
        fake_flow,
        [candidate],
        selected_uid="000000001",
    )

    fake_flow._async_schedule_integration_discovery_flow.assert_not_called()


async def test_async_migrate_entry_clears_legacy_data(
    hass: HomeAssistant,
) -> None:
    """v1→v2 migration clears legacy entry data; UID and title binding is deferred.

    ConfigEntryNotReady retry semantics only work inside async_setup_entry — raising
    from async_migrate_entry permanently lands the entry in MIGRATION_ERROR with no
    retry path.  All network-dependent work is therefore intentionally deferred to
    async_setup_entry.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={"host": "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    controller = create_mock_controller("000000001")

    with (
        patch_discovered_controllers(controller),
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {}
    assert entry.unique_id == "000000001"
    assert entry.title == "iZone 000000001"


async def test_async_migrate_entry_does_not_raise_on_discovery_failure(
    hass: HomeAssistant,
) -> None:
    """Migration succeeds without network calls regardless of discovery state.

    The retry-on-not-ready path only works in async_setup_entry; migration never
    makes network calls (see test_async_migrate_entry_clears_legacy_data).
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
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        side_effect=OSError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {}
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_async_migrate_entry_does_not_raise_for_multiple_eligible(
    hass: HomeAssistant,
) -> None:
    """Migration does not raise for multiple eligible controllers.

    The multi-controller failure case is handled in async_setup_entry, not here.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={"host": "192.0.2.1"},
    )
    entry.add_to_hass(hass)
    controller1 = create_mock_controller("000000001")
    controller2 = create_mock_controller("000000002", "192.0.2.2")

    with patch_discovered_controllers([controller1, controller2]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data == {}
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR


async def test_setup_entry_raises_not_ready_when_discovery_service_fails(
    hass: HomeAssistant,
) -> None:
    """async_setup_entry raises ConfigEntryNotReady when async_start_discovery_service raises OSError."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="000000001",
        data={CONF_HOST: "192.0.2.1"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        new=AsyncMock(side_effect=OSError),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("initial_title", "expected_title"),
    [
        pytest.param("iZone Aircon", "iZone 000000001", id="default_title_updated"),
        pytest.param("My AC", "My AC", id="custom_title_preserved"),
    ],
)
async def test_setup_entry_resolves_legacy_uid_and_updates_title(
    hass: HomeAssistant,
    initial_title: str,
    expected_title: str,
) -> None:
    """Legacy entry has its UID and title resolved at setup time, not migration time."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DOMAIN,
        title=initial_title,
        data={},
    )
    entry.add_to_hass(hass)
    controller = create_mock_controller("000000001", "192.0.2.2")

    with (
        patch_discovered_controllers(controller),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == "000000001"
    assert entry.title == expected_title


@pytest.mark.parametrize(
    ("return_value", "side_effect"),
    [
        pytest.param({}, None, id="no_controllers_found"),
        pytest.param(None, OSError, id="discovery_oserror"),
    ],
)
async def test_setup_entry_raises_not_ready_for_legacy_entry_on_discovery_failure(
    hass: HomeAssistant,
    return_value: dict | None,
    side_effect: type[Exception] | None,
) -> None:
    """Legacy entry raises ConfigEntryNotReady when discovery finds nothing or fails.

    Because this is raised from async_setup_entry (not async_migrate_entry), HA
    will schedule a retry — unlike the old behaviour where the exception would
    permanently land the entry in MIGRATION_ERROR.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
    )
    entry.add_to_hass(hass)

    if side_effect is OSError:
        patch_ctx = patch(
            "homeassistant.components.izone.discovery.async_start_discovery_service",
            side_effect=OSError,
        )
    else:
        patch_ctx = patch_discovered_controllers([])

    with patch_ctx:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_setup_entry_raises_config_error_for_legacy_entry_with_multiple_eligible(
    hass: HomeAssistant,
) -> None:
    """Legacy entry raises ConfigEntryError when multiple controllers are eligible.

    This is a permanent failure for the legacy entry.  The controllers are not lost —
    the discovery fan-out will surface them as individual flows once HA restarts.
    This is not a breaking change: a v1 entry with multiple controllers was already
    broken before this PR.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
    )
    entry.add_to_hass(hass)
    controllers = {
        "000000001": create_mock_controller("000000001", "192.0.2.1"),
        "000000002": create_mock_controller("000000002", "192.0.2.2"),
    }

    with patch_discovered_controllers(
        [controllers["000000001"], controllers["000000002"]]
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("excluded_uid", "already_configured_uid"),
    [
        pytest.param("000000001", "999999999", id="filtered_by_exclude_list"),
        pytest.param("999999999", "000000001", id="filtered_by_configured_entry"),
    ],
)
async def test_setup_entry_picks_eligible_controller_after_filtering_for_legacy_entry(
    hass: HomeAssistant,
    excluded_uid: str,
    already_configured_uid: str,
) -> None:
    """Legacy entry picks the one controller not filtered out.

    In each case one of two discovered controllers is ineligible — either its
    UID is in the exclude list or it is already owned by another config entry.
    The dummy UID "999999999" is used for the filter that should have no effect.
    """
    await async_load_yaml_exclude(hass, excluded_uid)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, version=2, unique_id=already_configured_uid, data={}
    ).add_to_hass(hass)
    controllers = {
        "000000001": create_mock_controller("000000001", "192.0.2.1"),
        "000000002": create_mock_controller("000000002", "192.0.2.2"),
    }

    with (
        patch_discovered_controllers(
            [controllers["000000001"], controllers["000000002"]]
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.unique_id == "000000002"
    assert entry.data == {}


@pytest.mark.parametrize(
    ("excluded_uid", "already_configured_uid"),
    [
        pytest.param("000000001", "999999999", id="all_excluded"),
        pytest.param("999999999", "000000001", id="all_already_configured"),
    ],
)
async def test_setup_entry_raises_not_ready_for_legacy_entry_when_no_eligible_after_filter(
    hass: HomeAssistant,
    excluded_uid: str,
    already_configured_uid: str,
) -> None:
    """Legacy entry raises ConfigEntryNotReady when all controllers are filtered out.

    HA will retry async_setup_entry, giving the user time to resolve the filter
    configuration.
    """
    await async_load_yaml_exclude(hass, excluded_uid)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DOMAIN,
        title="iZone Aircon",
        data={},
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, version=2, unique_id=already_configured_uid, data={}
    ).add_to_hass(hass)
    controller = create_mock_controller("000000001", "192.0.2.1")

    with patch_discovered_controllers(controller):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


def test_discovery_listener_methods_dispatch_expected_signals(
    hass: HomeAssistant,
) -> None:
    """Listener callbacks dispatch the expected Home Assistant signals."""
    service = izone_discovery.DiscoveryService(hass)
    controller = create_mock_controller("000000001", "192.0.2.1")
    zone = Mock()
    err = RuntimeError("boom")

    with patch(
        "homeassistant.components.izone.discovery.async_dispatcher_send"
    ) as mock_send:
        service.controller_disconnected(controller, err)
        service.controller_reconnected(controller)
        service.controller_update(controller)
        service.zone_update(controller, zone)

    assert mock_send.call_args_list == [
        ((hass, izone_discovery.DISPATCH_CONTROLLER_DISCONNECTED, controller, err),),
        ((hass, izone_discovery.DISPATCH_CONTROLLER_RECONNECTED, controller),),
        ((hass, izone_discovery.DISPATCH_CONTROLLER_UPDATE, controller),),
        ((hass, izone_discovery.DISPATCH_ZONE_UPDATE, controller, zone),),
    ]


async def test_start_discovery_listener_forwards_discovered_controller_to_flow(
    hass: HomeAssistant,
    mock_pizone_discovery_service: Mock,
) -> None:
    """Discovery dispatcher callback should forward discovered controllers to config flow."""
    captured_listener = None

    def _capture_listener(*args: object) -> Mock:
        nonlocal captured_listener
        captured_listener = args[2]
        return Mock()

    controller = create_mock_controller("000000004", "192.0.2.4")

    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.discovery",
            return_value=mock_pizone_discovery_service,
        ),
        patch(
            "homeassistant.components.izone.discovery.async_dispatcher_connect",
            side_effect=_capture_listener,
        ),
        patch(
            "homeassistant.components.izone.discovery.async_note_integration_discovery"
        ) as mock_note,
    ):
        await izone_discovery.async_start_discovery_service(hass)
        assert captured_listener is not None
        captured_listener(controller)

    mock_note.assert_called_once_with(hass, controller)

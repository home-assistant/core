"""Tests for iZone config flow."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import izone as izone_component
from homeassistant.components.izone import config_flow, discovery as izone_discovery
from homeassistant.components.izone.const import (
    DATA_CONFIG,
    DATA_DISCOVERY_SERVICE,
    IZONE,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _make_controller(uid: str = "000000001", ip: str = "192.0.2.1") -> Mock:
    """Return a minimal Mock iZone controller with uid and ip set."""
    controller = Mock()
    controller.device_uid = uid
    controller.device_ip = ip
    return controller


def _setup_shared_discovery(hass: HomeAssistant, *controllers: Mock) -> Mock:
    """Install a mock shared discovery service in hass.data and return it."""
    service = Mock()
    service.pi_disco.controllers = {c.device_uid: c for c in controllers}
    service.pi_disco.add_listener = Mock()
    service.pi_disco.remove_listener = Mock()
    service.pi_disco.rescan = AsyncMock()
    hass.data["izone_discovery"] = service
    return service


def _make_homekit_info(md: str, host: str | None = None) -> SimpleNamespace:
    """Return a minimal HomeKit discovery info object with attributes."""
    return SimpleNamespace(properties={"md": md}, host=host)


@pytest.fixture
def mock_entry_setup() -> Generator[None]:
    """Patch climate platform setup and discovery-service start for entry-creating tests."""
    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_izone_timeouts() -> Generator[None]:
    """Mock iZone timeout constants to speed up tests."""
    with (
        patch(
            "homeassistant.components.izone.config_flow.TIMEOUT_DISCOVERY",
            0.01,
        ),
        patch(
            "homeassistant.components.izone.discovery.DISCOVERY_IDLE_SECONDS",
            0.04,
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Config flow – user source (broadcast discovery)
# ---------------------------------------------------------------------------


async def test_found(hass: HomeAssistant, mock_entry_setup: None) -> None:
    """Test finding iZone controller via broadcast discovery."""
    controller = _make_controller(ip="192.0.2.1")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}


async def test_user_discovery_success(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test user flow confirms and creates an entry for a discovered controller."""
    controller = _make_controller("000000001", "192.0.2.55")
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}


async def test_user_discovery_default_selects_first_and_queues_other(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Default dropdown selection configures first UID and queues the other for confirm."""
    first = _make_controller("000000001", "192.0.2.1")
    second = _make_controller("000000002", "192.0.2.2")
    both = {first.device_uid: first, second.device_uid: second}

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value=both,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_controller"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000001"
    assert result["data"] == {}
    assert len(hass.config_entries.async_entries(IZONE)) == 1

    progress = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(IZONE)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(progress) == 1
    assert progress[0]["step_id"] == "confirm"
    assert progress[0]["context"]["unique_id"] == "000000002"


async def test_broadcast_skips_already_configured_controller(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test broadcast discovery skips configured controllers and sets up an unconfigured one."""
    configured_controller = _make_controller("000000001", "192.0.2.1")
    unconfigured_controller = _make_controller("000000002", "192.0.2.2")
    MockConfigEntry(
        domain=IZONE,
        unique_id=configured_controller.device_uid,
        data={"host": configured_controller.device_ip},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            configured_controller.device_uid: configured_controller,
            unconfigured_controller.device_uid: unconfigured_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}


async def test_broadcast_multiple_unconfigured_shows_choice(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test broadcast discovery shows a controller choice when multiple unconfigured controllers are found."""
    first_controller = _make_controller("000000002", "192.0.2.1")
    second_controller = _make_controller("000000001", "192.0.2.2")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            first_controller.device_uid: first_controller,
            second_controller.device_uid: second_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
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

    entries = hass.config_entries.async_entries(IZONE)
    assert len(entries) == 1
    assert entries[0].unique_id == "000000001"

    progress = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(IZONE)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(progress) == 1
    assert progress[0]["step_id"] == "confirm"
    assert progress[0]["context"]["unique_id"] == "000000002"


async def test_select_controller_aborts_when_choices_missing(
    hass: HomeAssistant,
) -> None:
    """Test controller selection aborts if the discovered controller choices are missing."""
    first_controller = _make_controller("000000001", "192.0.2.1")
    second_controller = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            first_controller.device_uid: first_controller,
            second_controller.device_uid: second_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
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
    first_controller = _make_controller("000000001", "192.0.2.1")
    second_controller = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            first_controller.device_uid: first_controller,
            second_controller.device_uid: second_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
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
    first_controller = _make_controller("000000002", "192.0.2.1")
    second_controller = _make_controller("000000001", "192.0.2.2")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            first_controller.device_uid: first_controller,
            second_controller.device_uid: second_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.SELECTED_CONTROLLER_UID: "000000002"},
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert len(hass.config_entries.async_entries(IZONE)) == 1

    skipped_flows = [
        p
        for p in hass.config_entries.flow.async_progress_by_handler(IZONE)
        if p["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    ]
    assert len(skipped_flows) == 1
    assert skipped_flows[0]["step_id"] == "confirm"
    assert skipped_flows[0]["context"]["unique_id"] == "000000001"


async def test_broadcast_aborts_when_all_discovered_are_configured(
    hass: HomeAssistant,
) -> None:
    """Test broadcast discovery aborts when every discovered controller is configured."""
    configured_controller = _make_controller("000000001", "192.0.2.1")
    MockConfigEntry(
        domain=IZONE,
        unique_id=configured_controller.device_uid,
        data={"host": configured_controller.device_ip},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={configured_controller.device_uid: configured_controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reuses_existing_discovery_service(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test config flow reuses the running discovery service without starting a new one."""
    controller = _make_controller("000000002", "192.0.2.2")
    _setup_shared_discovery(hass, controller)

    with patch(
        "homeassistant.components.izone.config_flow.pizone.discovery",
    ) as mock_pizone_discovery:
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}
    mock_pizone_discovery.assert_not_called()


async def test_user_discovery_uses_shared_discovery_service(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test user flow reuses the shared discovery snapshot (no temporary pizone)."""
    controller = _make_controller("000000002", "192.0.2.2")
    _setup_shared_discovery(hass, controller)

    with patch(
        "homeassistant.components.izone.config_flow.pizone.discovery",
    ) as mock_pizone_discovery:
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000000002"
    assert result["data"] == {}
    mock_pizone_discovery.assert_not_called()


# ---------------------------------------------------------------------------
# Config flow – import source
# ---------------------------------------------------------------------------


async def test_import_starts_discovery_service(
    hass: HomeAssistant,
) -> None:
    """Test YAML import starts discovery so runtime discovery can offer flows."""
    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        new=AsyncMock(),
    ) as mock_start:
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
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
            IZONE,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_import_aborts_when_another_izone_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test YAML import does not overlap discovery with an active user flow."""
    controller = _make_controller("000000001", "192.0.2.1")
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        user_flow = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        IZONE,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


# ---------------------------------------------------------------------------
# Config flow – HomeKit source
# ---------------------------------------------------------------------------


async def test_homekit_confirm_uses_discovered_host(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Test HomeKit flow confirms and uses the discovered controller IP, not the HomeKit host."""
    controller = _make_controller(ip="192.0.2.3")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
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


async def test_homekit_fans_out_other_discovered_controllers(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow fans out additional discovered controllers."""
    matched_controller = _make_controller("000000001", "192.0.2.3")
    other_controller = _make_controller("000000002", "192.0.2.4")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={
            matched_controller.device_uid: matched_controller,
            other_controller.device_uid: other_controller,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        await hass.async_block_till_done()

    progress = hass.config_entries.flow.async_progress_by_handler(IZONE)
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


async def test_homekit_proceeds_while_user_confirm_is_open(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """HomeKit onboarding for same UID is blocked while a user flow is already active."""
    controller = _make_controller("000000001", "192.0.2.3")
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        user_flow = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert user_flow["type"] is FlowResultType.FORM
        assert user_flow["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_user_broadcast_aborts_when_homekit_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test user broadcast discovery aborts when a HomeKit flow is already active."""
    controller = _make_controller("000000001", "192.0.2.3")
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        homekit_flow = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

        assert homekit_flow["type"] is FlowResultType.FORM
        assert homekit_flow["step_id"] == "confirm"

        user_flow = await hass.config_entries.flow.async_init(
            IZONE,
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
        domain=IZONE,
        unique_id="000000001",
        data={"host": "192.0.2.3"},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            IZONE,
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
    controller = _make_controller("000000001", "192.0.2.3")

    async def _discover_with_midflight_config(*args: object, **kwargs: object) -> dict:
        MockConfigEntry(
            domain=IZONE,
            unique_id="000000001",
            data={"host": "198.51.100.20"},
        ).add_to_hass(hass)
        return {controller.device_uid: controller}

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        side_effect=_discover_with_midflight_config,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_homekit_aborts_when_uid_not_found_in_discovery(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts when the discovered UID cannot be found via iZone discovery."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "192.0.2.3"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_uid_not_seen_on_lan_until_rediscover(
    hass: HomeAssistant,
) -> None:
    """HomeKit aborts if the advertised UID is missing from iZone discovery (even if it appears later)."""
    controller = _make_controller(ip="192.0.2.3")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        side_effect=[{}, {controller.device_uid: controller}],
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# ---------------------------------------------------------------------------
# Error / edge-case paths
# ---------------------------------------------------------------------------


async def test_not_found(hass: HomeAssistant) -> None:
    """Test abort when no device is found during broadcast discovery."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()


async def test_user_flow_abort_when_discovery_service_cannot_start(
    hass: HomeAssistant,
) -> None:
    """User flow aborts when discovery startup fails."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_discovery_with_shared_service_without_matches_aborts(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """User flow aborts when discovery refresh returns no controllers."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_without_model_aborts(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit flow with a non-iZone model string aborts immediately."""
    result = await hass.config_entries.flow.async_init(
        IZONE,
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
        "homeassistant.components.izone.config_flow._async_discover_controllers",
    ) as mock_discover_controllers:
        result = await hass.config_entries.flow.async_init(
            IZONE,
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
    controller = _make_controller("000000003", "192.0.2.33")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={controller.device_uid: controller},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_nothing_found(hass: HomeAssistant) -> None:
    """Test HomeKit aborts when iZone discovery finds no controllers."""
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_homekit_aborts_when_discovered_uid_missing(
    hass: HomeAssistant,
) -> None:
    """Test HomeKit aborts when discovery does not include the advertised UID."""
    different_controller = _make_controller("000000002", "192.0.2.44")

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        side_effect=[{}, {different_controller.device_uid: different_controller}],
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_make_homekit_info("iZone 000000001", "203.0.113.1"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_integration_discovery_aborts_on_invalid_payload(
    hass: HomeAssistant,
) -> None:
    """Test integration discovery aborts when uid/host are not strings."""
    result = await hass.config_entries.flow.async_init(
        IZONE,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={"uid": 1, "host": "192.0.2.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_runtime_integration_discovery_starts_confirm_flow(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """When the discovery service sees an unconfigured UID, offer setup."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000001",
        data={"host": "192.0.2.1"},
    ).add_to_hass(hass)
    new_ctrl = _make_controller("000000002", "192.0.2.2")

    config_flow.async_note_integration_discovery(hass, new_ctrl)
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(IZONE)
    assert len(progress) == 1
    assert (
        progress[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY
    )
    assert progress[0]["step_id"] == "confirm"


async def test_runtime_integration_discovery_skips_yaml_excluded_uid(
    hass: HomeAssistant,
) -> None:
    """Deprecated YAML exclude suppresses auto discovery flows."""
    hass.data[DATA_CONFIG] = {"exclude": ["000000002"]}
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000001",
        data={"host": "192.0.2.1"},
    ).add_to_hass(hass)
    excluded_ctrl = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        config_flow.async_note_integration_discovery(hass, excluded_ctrl)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_when_uid_already_configured(
    hass: HomeAssistant,
) -> None:
    """No discovery flow when a config entry already exists for the UID."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000002",
        data={"host": "192.0.2.2"},
    ).add_to_hass(hass)
    ctrl = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        config_flow.async_note_integration_discovery(hass, ctrl)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_for_ignored_unique_id(
    hass: HomeAssistant,
) -> None:
    """Ignored discoveries do not get a second integration discovery flow."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000002",
        source=config_entries.SOURCE_IGNORE,
        data={},
    ).add_to_hass(hass)
    ctrl = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        config_flow.async_note_integration_discovery(hass, ctrl)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_during_user_select_controller_step(
    hass: HomeAssistant,
) -> None:
    """Do not stack auto discovery while the user is choosing discovered controllers."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000001",
        data={"host": "192.0.2.1"},
    ).add_to_hass(hass)
    first = _make_controller("000000002", "192.0.2.2")
    second = _make_controller("000000003", "192.0.2.3")
    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={first.device_uid: first, second.device_uid: second},
    ):
        user_flow = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
    assert user_flow["type"] is FlowResultType.FORM
    assert user_flow["step_id"] == "select_controller"

    new_ctrl = _make_controller("000000002", "192.0.2.2")

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        config_flow.async_note_integration_discovery(hass, new_ctrl)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_create_flow.assert_not_called()


async def test_runtime_integration_discovery_skips_during_user_confirm(
    hass: HomeAssistant, mock_entry_setup: None
) -> None:
    """Runtime discovery stays suppressed while an interactive user flow is active."""
    first = _make_controller("000000001", "192.0.2.1")
    second = _make_controller("000000002", "192.0.2.2")
    one = {first.device_uid: first}

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value=one,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "confirm"

    config_flow.async_note_integration_discovery(hass, second)
    await hass.async_block_till_done(wait_background_tasks=True)

    progress = hass.config_entries.flow.async_progress_by_handler(IZONE)
    assert len(progress) == 1
    assert progress[0]["context"]["source"] == config_entries.SOURCE_USER


# ---------------------------------------------------------------------------
# Lifecycle / setup integration
# ---------------------------------------------------------------------------


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
        assert await izone_component.async_setup(hass, {IZONE: {"exclude": []}})

    mock_async_init.assert_called_once_with(
        IZONE, context={"source": config_entries.SOURCE_IMPORT}
    )
    mock_create_task.assert_called_once()


async def test_async_setup_entry_stops_discovery_on_forward_failure(
    hass: HomeAssistant,
) -> None:
    """Test discovery service is stopped when platform forward setup fails."""
    entry = MockConfigEntry(domain=IZONE, data={"host": "192.0.2.1"})

    with (
        pytest.raises(RuntimeError, match="boom"),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ) as mock_start,
        patch(
            "homeassistant.components.izone.async_stop_discovery_service",
            return_value=None,
        ) as mock_stop,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=RuntimeError("boom"),
        ),
    ):
        await izone_component.async_setup_entry(hass, entry)

    mock_start.assert_awaited_once()
    mock_stop.assert_awaited_once()


async def test_async_start_discovery_service_stops_on_home_assistant_stop(
    hass: HomeAssistant,
    mock_pizone_discovery_service: Mock,
) -> None:
    """Test discovery service is stopped on Home Assistant shutdown."""
    with (
        patch(
            "homeassistant.components.izone.discovery.aiohttp_client.async_get_clientsession",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.components.izone.discovery.pizone.discovery",
            return_value=mock_pizone_discovery_service,
        ),
    ):
        await izone_discovery.async_start_discovery_service(hass)

        assert DATA_DISCOVERY_SERVICE in hass.data

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    mock_pizone_discovery_service.start_discovery.assert_awaited_once()
    mock_pizone_discovery_service.close.assert_awaited_once()
    assert DATA_DISCOVERY_SERVICE not in hass.data


async def test_async_maybe_stop_keeps_running_when_actionable_flow_exists(
    hass: HomeAssistant,
) -> None:
    """Discovery should stay running while an actionable iZone flow is in progress."""
    service = Mock()
    service.pi_disco.controllers = {}
    service.async_schedule_idle_stop = Mock()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with (
        patch.object(
            hass.config_entries.flow,
            "async_progress_by_handler",
            return_value=[{"context": {"source": config_entries.SOURCE_USER}}],
        ),
        patch(
            "homeassistant.components.izone.discovery.async_stop_discovery_service",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_not_awaited()
    service.async_schedule_idle_stop.assert_called_once()


async def test_async_maybe_stop_keeps_running_when_actionable_entry_exists(
    hass: HomeAssistant,
) -> None:
    """Discovery should stay running while an enabled, non-ignored entry exists."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        data={},
    ).add_to_hass(hass)

    service = Mock()
    service.pi_disco.controllers = {}
    service.async_schedule_idle_stop = Mock()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with patch(
        "homeassistant.components.izone.discovery.async_stop_discovery_service",
        new=AsyncMock(),
    ) as mock_stop:
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_not_awaited()
    service.async_schedule_idle_stop.assert_called_once()


async def test_async_maybe_stop_stops_when_only_disabled_entry_matches_controller(
    hass: HomeAssistant,
) -> None:
    """Discovery should stop when only disabled/ignored controllers remain."""
    MockConfigEntry(
        domain=IZONE,
        unique_id="000000001",
        source=config_entries.SOURCE_USER,
        disabled_by=config_entries.ConfigEntryDisabler.USER,
        data={},
    ).add_to_hass(hass)

    service = Mock()
    service.pi_disco.controllers = {"000000001": _make_controller("000000001")}
    service.async_schedule_idle_stop = Mock()
    hass.data[DATA_DISCOVERY_SERVICE] = service

    with patch(
        "homeassistant.components.izone.discovery.async_stop_discovery_service",
        new=AsyncMock(),
    ) as mock_stop:
        await izone_discovery.async_maybe_stop_discovery_service(hass)

    mock_stop.assert_awaited_once_with(hass)
    service.async_schedule_idle_stop.assert_not_called()


async def test_async_setup_entry_migrates_legacy_entry(
    hass: HomeAssistant,
) -> None:
    """Test legacy config entries are migrated to the discovered controller UID."""
    entry = MockConfigEntry(domain=IZONE, unique_id=IZONE, data={})
    entry.add_to_hass(hass)
    controller = _make_controller("000000001", "192.0.2.1")

    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={controller.device_uid: controller},
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ) as mock_start,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=None,
        ) as mock_forward,
    ):
        await izone_component.async_setup_entry(hass, entry)

    assert entry.unique_id == controller.device_uid
    assert entry.data == {}
    mock_start.assert_awaited_once()
    mock_forward.assert_awaited_once()


async def test_async_setup_entry_migrates_legacy_entry_ignoring_excluded_controllers(
    hass: HomeAssistant,
) -> None:
    """Test legacy config entry migration ignores controllers excluded in YAML."""
    entry = MockConfigEntry(domain=IZONE, unique_id=IZONE, data={})
    entry.add_to_hass(hass)
    excluded_controller = _make_controller("000000001", "192.0.2.1")
    remaining_controller = _make_controller("000000002", "192.0.2.2")
    hass.data[DATA_CONFIG] = {"exclude": [excluded_controller.device_uid]}

    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={
                excluded_controller.device_uid: excluded_controller,
                remaining_controller.device_uid: remaining_controller,
            },
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=None,
        ),
    ):
        await izone_component.async_setup_entry(hass, entry)

    assert entry.unique_id == remaining_controller.device_uid
    assert entry.data == {}


async def test_async_setup_entry_legacy_entry_not_ready_when_no_eligible_controller(
    hass: HomeAssistant,
) -> None:
    """Test legacy config entry migration waits when no eligible controllers are found."""
    entry = MockConfigEntry(domain=IZONE, unique_id=IZONE, data={})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={},
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await izone_component.async_setup_entry(hass, entry)


async def test_async_setup_entry_legacy_entry_errors_when_multiple_eligible_controllers(
    hass: HomeAssistant,
) -> None:
    """Test legacy config entry migration errors when multiple eligible controllers are found."""
    entry = MockConfigEntry(domain=IZONE, unique_id=IZONE, data={})
    entry.add_to_hass(hass)
    first_controller = _make_controller("000000001", "192.0.2.1")
    second_controller = _make_controller("000000002", "192.0.2.2")

    with (
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={
                first_controller.device_uid: first_controller,
                second_controller.device_uid: second_controller,
            },
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
        pytest.raises(ConfigEntryError),
    ):
        await izone_component.async_setup_entry(hass, entry)


# ---------------------------------------------------------------------------
# Helper / internals unit tests
# ---------------------------------------------------------------------------


async def test_async_discover_controllers_starts_shared_service_when_missing(
    hass: HomeAssistant,
) -> None:
    """Starting discovery without refresh does not trigger extra wait/rescan work."""
    controller = _make_controller(ip="192.0.2.3")
    service = _setup_shared_discovery(hass, controller)
    del hass.data[DATA_DISCOVERY_SERVICE]

    with patch(
        "homeassistant.components.izone.discovery.async_start_discovery_service",
        return_value=service,
    ) as mock_start:
        controllers = await config_flow._async_discover_controllers(hass)

    assert list(controllers) == ["000000001"]
    mock_start.assert_awaited_once()
    service.pi_disco.rescan.assert_not_awaited()
    service.pi_disco.add_listener.assert_not_called()
    service.pi_disco.remove_listener.assert_not_called()


async def test_async_discover_controllers_refresh_after_start_waits_without_rescan(
    hass: HomeAssistant,
) -> None:
    """Refresh after start waits for discovery but skips a duplicate rescan."""
    controller = _make_controller(ip="192.0.2.3")
    service = _setup_shared_discovery(hass, controller)
    del hass.data[DATA_DISCOVERY_SERVICE]

    with (
        patch(
            "homeassistant.components.izone.discovery.async_start_discovery_service",
            return_value=service,
        ) as mock_start,
        patch(
            "homeassistant.components.izone.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ) as mock_sleep,
    ):
        controllers = await config_flow._async_discover_controllers(hass, refresh=True)

    assert list(controllers) == ["000000001"]
    mock_start.assert_awaited_once()
    mock_sleep.assert_awaited_once()  # Called with mocked timeout constant
    service.pi_disco.rescan.assert_not_awaited()
    service.pi_disco.add_listener.assert_not_called()
    service.pi_disco.remove_listener.assert_not_called()


async def test_async_discover_controllers_refresh_rescans_shared_service(
    hass: HomeAssistant,
) -> None:
    """Refresh without UID waits the full timeout after rescan."""
    service = _setup_shared_discovery(hass)  # start with no controllers

    with patch(
        "homeassistant.components.izone.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep:
        controllers = await config_flow._async_discover_controllers(hass, refresh=True)

    assert controllers == {}
    service.pi_disco.rescan.assert_awaited_once()
    mock_sleep.assert_awaited_once()  # Called with mocked timeout constant
    service.pi_disco.add_listener.assert_not_called()
    service.pi_disco.remove_listener.assert_not_called()


async def test_async_discover_controllers_refresh_skips_when_uid_already_known(
    hass: HomeAssistant,
) -> None:
    """Skip rescan when caller only needs a UID that is already known."""
    known = _make_controller("000000001", "192.0.2.3")
    service = _setup_shared_discovery(hass, known)

    controllers = await config_flow._async_discover_controllers(
        hass,
        refresh=True,
        wait_for_uid="000000001",
    )

    assert controllers == {"000000001": known}
    service.pi_disco.rescan.assert_not_awaited()
    service.pi_disco.add_listener.assert_not_called()
    service.pi_disco.remove_listener.assert_not_called()


async def test_async_discover_controllers_waits_for_requested_uid(
    hass: HomeAssistant,
) -> None:
    """Refresh listener completes early when the requested UID is discovered."""
    service = _setup_shared_discovery(hass)
    requested = _make_controller("000000777", "192.0.2.77")

    def _add_listener(listener: object) -> None:
        service.pi_disco.controllers[requested.device_uid] = requested
        listener.controller_discovered(requested)

    service.pi_disco.add_listener.side_effect = _add_listener

    with patch(
        "homeassistant.components.izone.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep:
        controllers = await config_flow._async_discover_controllers(
            hass,
            refresh=True,
            wait_for_uid="000000777",
        )

    assert controllers == {requested.device_uid: requested}
    service.pi_disco.rescan.assert_awaited_once()
    service.pi_disco.add_listener.assert_called_once()
    service.pi_disco.remove_listener.assert_called_once()
    mock_sleep.assert_not_awaited()

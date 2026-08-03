"""Test the Teslemetry update platform."""

import copy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.components.teslemetry.update import INSTALLING
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import assert_entities, reload_platform, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA, VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed, mock_restore_cache


async def test_update(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.UPDATE])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_update_services(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the update services work."""

    await setup_platform(hass, [Platform.UPDATE])

    entity_id = "update.test_update"

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.schedule_software_update",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        call.assert_called_once()

    VEHICLE_INSTALLING = copy.deepcopy(VEHICLE_DATA)
    VEHICLE_INSTALLING["response"]["vehicle_state"]["software_update"]["status"] = (
        INSTALLING
    )
    mock_vehicle_data.return_value = VEHICLE_INSTALLING
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["in_progress"] == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the select entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 50,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] == 50
    assert state == snapshot(name="downloading")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 1,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    # Install percentages up to 10% reflect Tesla's pre-installation step, not real progress
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None
    assert state == snapshot(name="ready")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 50,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] == 50
    assert state == snapshot(name="installing")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "2025.2.1",
                Signal.VERSION: "2025.1.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    # 100% installed is complete, not in progress
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None
    assert state == snapshot(name="install_complete")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
                Signal.SOFTWARE_UPDATE_VERSION: "",
                Signal.VERSION: "2025.2.1",
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None
    assert state == snapshot(name="updated")

    await reload_platform(hass, entry, [Platform.UPDATE])

    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is False
    assert state.attributes["update_percentage"] is None
    assert state == snapshot(name="restored")


async def test_update_streaming_scheduled_not_clobbered(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Test that a scheduled install stays in progress until real progress or cancellation."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.UPDATE])

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: 1735689600,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] is None
    assert state == snapshot(name="scheduled")

    # Download begins and the schedule clears in the same payload: progress must win
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 5,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] == 5
    assert state == snapshot(name="downloading_after_schedule_cleared")


async def test_update_streaming_restore(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Test that the streaming update entity restores update_percentage, not install_percentage."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entity_id = "update.test_update"
    mock_restore_cache(
        hass,
        (
            State(
                entity_id,
                STATE_ON,
                attributes={
                    "in_progress": True,
                    "update_percentage": 42,
                    "installed_version": "2025.1.1",
                    "latest_version": "2025.2.1",
                },
            ),
        ),
    )

    await setup_platform(hass, [Platform.UPDATE])

    state = hass.states.get(entity_id)
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] == 42


@pytest.mark.parametrize(
    ("data", "expected_in_progress", "expected_percentage"),
    [
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 0,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            False,
            None,
            id="download_0pct_is_idle",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 1,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            True,
            1,
            id="download_1pct_is_in_progress",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: None,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            False,
            None,
            id="download_100pct_is_complete",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 1,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            False,
            None,
            id="install_1pct_is_not_in_progress",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 10,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            False,
            None,
            id="install_10pct_is_not_in_progress",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 11,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            True,
            11,
            id="install_11pct_is_in_progress",
        ),
        pytest.param(
            {
                Signal.SOFTWARE_UPDATE_DOWNLOAD_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_INSTALLATION_PERCENT_COMPLETE: 100,
                Signal.SOFTWARE_UPDATE_SCHEDULED_START_TIME: None,
            },
            False,
            None,
            id="install_100pct_is_complete",
        ),
    ],
)
async def test_update_streaming_progress_thresholds(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
    data: dict[Signal, int | None],
    expected_in_progress: bool,
    expected_percentage: int | None,
) -> None:
    """Test download/install progress threshold edge cases."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    await setup_platform(hass, [Platform.UPDATE])

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": data,
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.attributes["in_progress"] is expected_in_progress
    assert state.attributes["update_percentage"] == expected_percentage

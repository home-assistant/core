"""Tests for the Portainer event platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer import PortainerEventListenerResult
from pyportainer.models.docker import PortainerImageUpdateStatus
from pyportainer.models.docker_inspect import DockerInspect
from pyportainer.models.event import DockerEvent, DockerEventActor
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import CONTAINER_STATE_EVENT_TYPES, DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import TEST_CONTAINER_ID, TEST_CONTAINER_NAME

from tests.common import MockConfigEntry, load_json_value_fixture, snapshot_platform


async def _fire_event(
    hass: HomeAssistant,
    mock_portainer_event_listeners: dict[int, MagicMock],
    endpoint_id: int,
    action: str,
    actor_id: str | None = None,
    event_type: str = "container",
    actor_attributes: dict[str, str] | None = None,
) -> None:
    """Invoke the coordinator's registered event callback with a synthetic event."""
    event = DockerEvent(
        type=event_type,
        action=action,
        actor=DockerEventActor(id=actor_id, attributes=actor_attributes)
        if actor_id or actor_attributes
        else None,
    )
    listener = mock_portainer_event_listeners[endpoint_id]
    callback = listener.register_callback.call_args[0][0]
    await callback(PortainerEventListenerResult(endpoint_id=endpoint_id, event=event))
    await hass.async_block_till_done()


TEST_EVENT_ENTITY_ID = f"event.{TEST_CONTAINER_NAME}_docker_event"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all event entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.EVENT],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.parametrize("expected_event_type", CONTAINER_STATE_EVENT_TYPES)
async def test_state_event_triggers_entity_event(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_event_listeners: dict[int, MagicMock],
    mock_config_entry: MockConfigEntry,
    expected_event_type: str,
) -> None:
    """Test a state Docker event fires the container's event entity."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(TEST_EVENT_ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    inspect = cast(
        dict[str, Any], load_json_value_fixture("container_inspect.json", DOMAIN)
    )
    mock_portainer_client.inspect_container.return_value = DockerInspect.from_dict(
        inspect
    )

    action = (
        f"health_status: {expected_event_type.removeprefix('health_status_')}"
        if expected_event_type.startswith("health_status_")
        else expected_event_type
    )
    await _fire_event(
        hass,
        mock_portainer_event_listeners,
        1,
        action,
        TEST_CONTAINER_ID,
    )

    assert (state := hass.states.get(TEST_EVENT_ENTITY_ID))
    assert state.attributes["event_type"] == expected_event_type
    assert state.state == dt_util.utcnow().isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("mock_portainer_client")
async def test_ignored_action_does_not_change_data(
    hass: HomeAssistant,
    mock_portainer_event_listeners: dict[int, MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a noisy/irrelevant Docker event doesn't change coordinator data."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    data_before = coordinator.data

    await _fire_event(
        hass,
        mock_portainer_event_listeners,
        1,
        "exec_start",
        TEST_CONTAINER_ID,
    )

    assert coordinator.data is data_before


@pytest.mark.usefixtures("mock_portainer_client")
async def test_unknown_container_id_does_not_change_data(
    hass: HomeAssistant,
    mock_portainer_event_listeners: dict[int, MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a state event for an untracked actor id is silently ignored."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    data_before = coordinator.data

    await _fire_event(
        hass,
        mock_portainer_event_listeners,
        1,
        "start",
        "unknown-container-id",
    )

    assert coordinator.data is data_before


@pytest.mark.usefixtures("mock_portainer_client")
async def test_recreated_container_restores_image_status(
    hass: HomeAssistant,
    mock_portainer_event_listeners: dict[int, MagicMock],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a recreated container's image status is restored by its start event.

    A recreated container keeps its name but gets a new container id, which the
    id map built at the last refresh does not know. Docker carries the container
    name in the event attributes, so the update entity recovers instead of
    reporting unknown until the next 24 hour watcher cycle. See #182584.
    """
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # The recreate path queries the API directly, so give it a concrete status.
    expected_status = PortainerImageUpdateStatus(
        update_available=True,
        local_digest="sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96",
        registry_digest="sha256:newdigest123456789",
    )
    coordinator.portainer.container_image_status = AsyncMock(
        return_value=expected_status
    )

    # funny_chatelet is the fixture container the mock watcher has a result for.
    container_name = "funny_chatelet"
    tracked_id = next(
        id_
        for id_, name in coordinator._container_ids_by_endpoint[1].items()
        if name == container_name
    )
    assert (1, tracked_id) in coordinator.watcher.results
    data_before = coordinator.data[1].containers[container_name]
    assert data_before.image_status is not None

    # Recreate: a fresh id that is in neither the id map nor the watcher results.
    new_id = "new-container-id-after-recreate"
    assert (1, new_id) not in coordinator.watcher.results

    await _fire_event(
        hass,
        mock_portainer_event_listeners,
        1,
        "start",
        new_id,
        actor_attributes={"name": container_name, "image": "alpine"},
    )

    # The new id is now tracked and the image status is preserved.
    assert coordinator._container_ids_by_endpoint[1][new_id] == container_name
    data_after = coordinator.data[1].containers[container_name]
    assert data_after.image_status is not None
    assert data_after.image_status == data_before.image_status

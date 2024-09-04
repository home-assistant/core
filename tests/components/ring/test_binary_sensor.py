"""The tests for the Ring binary sensor platform."""

import time
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.ring.binary_sensor import RingEvent
from homeassistant.components.ring.const import DOMAIN
from homeassistant.components.ring.coordinator import RingEventListener
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .common import setup_automation, setup_platform
from .device_mocks import FRONT_DOOR_DEVICE_ID, INGRESS_DEVICE_ID

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("device_id", "device_name", "alert_kind", "device_class"),
    [
        pytest.param(
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "motion",
            "motion",
            id="front_door_motion",
        ),
        pytest.param(
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "ding",
            "occupancy",
            id="front_door_ding",
        ),
        pytest.param(
            INGRESS_DEVICE_ID, "ingress", "ding", "occupancy", id="ingress_ding"
        ),
    ],
)
async def test_binary_sensor_without_deprecation(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_event_listener_class: RingEventListener,
    freezer: FrozenDateTimeFactory,
    device_id,
    device_name,
    alert_kind,
    device_class,
) -> None:
    """Test the Ring binary sensors as if they were not deprecated."""
    with patch(
        "homeassistant.components.ring.binary_sensor.async_check_create_deprecated",
        return_value=True,
    ):
        await setup_platform(hass, Platform.BINARY_SENSOR)

    on_event_cb = mock_ring_event_listener_class.return_value.add_notification_callback.call_args.args[
        0
    ]

    # Default state is set to off
    entity_id = f"binary_sensor.{device_name}_{alert_kind}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["device_class"] == device_class

    # A new alert sets to on
    event = RingEvent(
        1234546, device_id, "Foo", "Bar", time.time(), 180, kind=alert_kind, state=None
    )
    mock_ring_client.active_alerts.return_value = [event]
    on_event_cb(event)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Test that another event resets the expiry callback
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    event = RingEvent(
        1234546, device_id, "Foo", "Bar", time.time(), 180, kind=alert_kind, state=None
    )
    mock_ring_client.active_alerts.return_value = [event]
    on_event_cb(event)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    freezer.tick(120)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Test the second alert has expired
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_not_exists_with_deprecation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_ring_client,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the deprecated Ring binary sensors are deleted or raise issues."""
    mock_config_entry.add_to_hass(hass)

    entity_id = "binary_sensor.front_door_motion"

    assert not hass.states.get(entity_id)
    with patch("homeassistant.components.ring.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await async_setup_component(hass, DOMAIN, {})

    assert not entity_registry.async_get(entity_id)
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("entity_disabled", "entity_has_automations"),
    [
        pytest.param(False, False, id="without-automations"),
        pytest.param(False, True, id="with-automations"),
        pytest.param(True, False, id="disabled"),
    ],
)
async def test_binary_sensor_exists_with_deprecation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_ring_client,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_disabled,
    entity_has_automations,
) -> None:
    """Test the deprecated Ring binary sensors are deleted or raise issues."""
    mock_config_entry.add_to_hass(hass)

    entity_id = "binary_sensor.front_door_motion"
    unique_id = f"{FRONT_DOOR_DEVICE_ID}-motion"
    issue_id = f"deprecated_entity_{entity_id}_automation.test_automation"

    if entity_has_automations:
        await setup_automation(hass, "test_automation", entity_id)

    entity = entity_registry.async_get_or_create(
        domain=BINARY_SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=unique_id,
        suggested_object_id="front_door_motion",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER if entity_disabled else None,
    )
    assert entity.entity_id == entity_id
    assert not hass.states.get(entity_id)
    with patch("homeassistant.components.ring.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await async_setup_component(hass, DOMAIN, {})

    entity = entity_registry.async_get(entity_id)
    # entity and state will be none if removed from registry
    assert (entity is None) == entity_disabled
    assert (hass.states.get(entity_id) is None) == entity_disabled

    assert (
        issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    ) == entity_has_automations

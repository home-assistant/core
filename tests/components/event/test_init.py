"""The tests for the event integration."""

from collections.abc import Generator
from typing import Any

from freezegun import freeze_time
import pytest

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PLATFORM, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import TEST_DOMAIN

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_restore_state_shutdown_restart,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)


async def test_event() -> None:
    """Test the event entity."""
    event = EventEntity()
    event.entity_id = "event.doorbell"
    # Test event with no data at all
    assert event.state is None
    assert event.state_attributes == {ATTR_EVENT_TYPE: None}
    assert not event.extra_state_attributes
    assert event.device_class is None

    # No event types defined, should raise
    with pytest.raises(AttributeError):
        _ = event.event_types

    # Test retrieving data from entity description
    event.entity_description = EventEntityDescription(
        key="test_event",
        event_types=["short_press", "long_press"],
        device_class=EventDeviceClass.DOORBELL,
    )
    # Delete the cache since we changed the entity description
    # at run time
    del event.device_class
    assert event.event_types == ["short_press", "long_press"]
    assert event.device_class == EventDeviceClass.DOORBELL

    # Test attrs win over entity description
    event._attr_event_types = ["short_press", "long_press", "double_press"]
    assert event.event_types == ["short_press", "long_press", "double_press"]
    event._attr_device_class = EventDeviceClass.BUTTON
    assert event.device_class == EventDeviceClass.BUTTON

    # Test triggering an event
    now = dt_util.utcnow()
    with freeze_time(now):
        event._trigger_event("long_press")

        assert event.state == now.isoformat(timespec="milliseconds")
        assert event.state_attributes == {ATTR_EVENT_TYPE: "long_press"}
        assert not event.extra_state_attributes

    # Test triggering an event, with extra attribute data
    now = dt_util.utcnow()
    with freeze_time(now):
        event._trigger_event("short_press", {"hello": "world"})

        assert event.state == now.isoformat(timespec="milliseconds")
        assert event.state_attributes == {
            ATTR_EVENT_TYPE: "short_press",
            "hello": "world",
        }

    # Test triggering an unknown event
    with pytest.raises(
        ValueError, match="^Invalid event type unknown_event for event.doorbell$"
    ):
        event._trigger_event("unknown_event")


@pytest.mark.usefixtures("enable_custom_integrations", "mock_event_platform")
async def test_restore_state(hass: HomeAssistant) -> None:
    """Test we restore state integration."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "event.doorbell",
                    "2021-01-01T23:59:59.123+00:00",
                    attributes={
                        ATTR_EVENT_TYPE: "ignored",
                        ATTR_EVENT_TYPES: [
                            "single_press",
                            "double_press",
                            "do",
                            "not",
                            "restore",
                        ],
                        "hello": "worm",
                    },
                ),
                {
                    "last_event_type": "double_press",
                    "last_event_attributes": {
                        "hello": "world",
                    },
                },
            ),
        ),
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("event.doorbell")
    assert state
    assert state.state == "2021-01-01T23:59:59.123+00:00"
    assert state.attributes[ATTR_EVENT_TYPES] == ["short_press", "long_press"]
    assert state.attributes[ATTR_EVENT_TYPE] == "double_press"
    assert state.attributes["hello"] == "world"


@pytest.mark.usefixtures("enable_custom_integrations", "mock_event_platform")
async def test_invalid_extra_restore_state(hass: HomeAssistant) -> None:
    """Test we restore state integration."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "event.doorbell",
                    "2021-01-01T23:59:59.123+00:00",
                ),
                {
                    "invalid_unexpected_key": "double_press",
                    "last_event_attributes": {
                        "hello": "world",
                    },
                },
            ),
        ),
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("event.doorbell")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPES] == ["short_press", "long_press"]
    assert state.attributes[ATTR_EVENT_TYPE] is None
    assert "hello" not in state.attributes


@pytest.mark.usefixtures("enable_custom_integrations", "mock_event_platform")
async def test_no_extra_restore_state(hass: HomeAssistant) -> None:
    """Test we restore state integration."""
    mock_restore_cache(
        hass,
        (
            State(
                "event.doorbell",
                "2021-01-01T23:59:59.123+00:00",
                attributes={
                    ATTR_EVENT_TYPES: [
                        "single_press",
                        "double_press",
                    ],
                    ATTR_EVENT_TYPE: "double_press",
                    "hello": "world",
                },
            ),
        ),
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("event.doorbell")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPES] == ["short_press", "long_press"]
    assert state.attributes[ATTR_EVENT_TYPE] is None
    assert "hello" not in state.attributes


@pytest.mark.usefixtures("enable_custom_integrations", "mock_event_platform")
async def test_saving_state(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test we restore state integration."""
    restore_data = {"last_event_type": "double_press", "last_event_attributes": None}

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "event.doorbell",
                    "2021-01-01T23:59:59.123+00:00",
                ),
                restore_data,
            ),
        ),
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == "event.doorbell"
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == restore_data


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.mark.usefixtures("config_flow_fixture")
async def test_name(hass: HomeAssistant) -> None:
    """Test event name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed event without device class -> no name
    entity1 = EventEntity()
    entity1._attr_event_types = ["ding"]
    entity1.entity_id = "event.test1"

    # Unnamed event with device class but has_entity_name False -> no name
    entity2 = EventEntity()
    entity2._attr_event_types = ["ding"]
    entity2.entity_id = "event.test2"
    entity2._attr_device_class = EventDeviceClass.DOORBELL

    # Unnamed event with device class and has_entity_name True -> named
    entity3 = EventEntity()
    entity3._attr_event_types = ["ding"]
    entity3.entity_id = "event.test3"
    entity3._attr_device_class = EventDeviceClass.DOORBELL
    entity3._attr_has_entity_name = True

    # Unnamed event with device class and has_entity_name True -> named
    entity4 = EventEntity()
    entity4._attr_event_types = ["ding"]
    entity4.entity_id = "event.test4"
    entity4.entity_description = EventEntityDescription(
        "test",
        EventDeviceClass.DOORBELL,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test event platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state
    assert state.attributes == {"event_types": ["ding"], "event_type": None}

    state = hass.states.get(entity2.entity_id)
    assert state
    assert state.attributes == {
        "event_types": ["ding"],
        "event_type": None,
        "device_class": "doorbell",
    }

    state = hass.states.get(entity3.entity_id)
    assert state
    assert state.attributes == {
        "event_types": ["ding"],
        "event_type": None,
        "device_class": "doorbell",
        "friendly_name": "Doorbell",
    }

    state = hass.states.get(entity4.entity_id)
    assert state
    assert state.attributes == {
        "event_types": ["ding"],
        "event_type": None,
        "device_class": "doorbell",
        "friendly_name": "Doorbell",
    }

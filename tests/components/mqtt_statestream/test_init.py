"""The tests for the MQTT statestream component."""

from unittest.mock import ANY, call

import pytest

from homeassistant.components import mqtt_statestream as statestream
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.setup import async_setup_component

from tests.common import MockEntity, MockEntityPlatform, mock_state_change_event
from tests.typing import MqttMockHAClient


async def add_statestream(
    hass: HomeAssistant,
    base_topic=None,
    publish_attributes=None,
    publish_timestamps=None,
    publish_include=None,
    publish_exclude=None,
) -> bool:
    """Add a mqtt_statestream component."""
    config = {}
    if base_topic:
        config["base_topic"] = base_topic
    if publish_attributes:
        config["publish_attributes"] = publish_attributes
    if publish_timestamps:
        config["publish_timestamps"] = publish_timestamps
    if publish_include:
        config["include"] = publish_include
    if publish_exclude:
        config["exclude"] = publish_exclude
    return await async_setup_component(
        hass, statestream.DOMAIN, {statestream.DOMAIN: config}
    )


async def test_fails_with_no_base(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Setup should fail if no base_topic is set."""
    assert await add_statestream(hass) is False


async def test_setup_succeeds_without_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the success of the setup with a valid base_topic."""
    assert await add_statestream(hass, base_topic="pub")


async def test_setup_and_stop_waits_for_ha(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the success of the setup with a valid base_topic."""
    e_id = "fake.entity"

    # HA is not running
    hass.set_state(CoreState.not_running)

    assert await add_statestream(hass, base_topic="pub")
    await hass.async_block_till_done()
    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was not published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_not_called()

    # HA is starting up
    await hass.async_start()
    await hass.async_block_till_done()

    # Change a state of an entity
    mock_state_change_event(hass, State(e_id, "off"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "off", 1, True)
    assert mqtt_mock.async_publish.called
    mqtt_mock.reset_mock()

    # HA is shutting down
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Change a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was not published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_not_called()


# We use xfail with this test because there is an unhandled exception
# in a background task in this test.
# The exception is raised by mqtt.async_publish.
@pytest.mark.xfail
async def test_startup_no_mqtt(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test startup without MQTT support."""
    e_id = "fake.entity"

    assert await add_statestream(hass, base_topic="pub")
    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert "MQTT is not enabled" in caplog.text


async def test_setup_succeeds_with_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test setup with a valid base_topic and publish_attributes."""
    assert await add_statestream(hass, base_topic="pub", publish_attributes=True)


async def test_state_changed_event_sends_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the sending of a new message if event changed."""
    e_id = "fake.entity"
    base_topic = "pub"

    # Add the statestream component for publishing state updates
    assert await add_statestream(hass, base_topic=base_topic)
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called
    mqtt_mock.async_publish.reset_mock()

    # Create a test entity and add it to hass
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_called_with(
        "pub/test_domain/test_platform_1234/state", "unknown", 1, True
    )
    mqtt_mock.async_publish.reset_mock()

    state = hass.states.get("test_domain.test_platform_1234")
    assert state is not None

    # Now remove it, nothing should be published
    hass.states.async_remove("test_domain.test_platform_1234")
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_not_called()


async def test_state_changed_event_sends_message_and_timestamp(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the sending of a message and timestamps if event changed."""
    e_id = "another.entity"
    base_topic = "pub"

    # Add the statestream component for publishing state updates
    assert await add_statestream(
        hass, base_topic=base_topic, publish_attributes=None, publish_timestamps=True
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    calls = [
        call.async_publish("pub/another/entity/state", "on", 1, True),
        call.async_publish("pub/another/entity/last_changed", ANY, 1, True),
        call.async_publish("pub/another/entity/last_updated", ANY, 1, True),
    ]

    mqtt_mock.async_publish.assert_has_calls(calls, any_order=True)
    assert mqtt_mock.async_publish.called


async def test_state_changed_attr_sends_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the sending of a new message if attribute changed."""
    e_id = "fake.entity"
    base_topic = "pub"

    # Add the statestream component for publishing state updates
    assert await add_statestream(hass, base_topic=base_topic, publish_attributes=True)
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    test_attributes = {"testing": "YES", "list": ["a", "b", "c"], "bool": False}

    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "off", attributes=test_attributes))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    calls = [
        call.async_publish("pub/fake/entity/state", "off", 1, True),
        call.async_publish("pub/fake/entity/testing", '"YES"', 1, True),
        call.async_publish("pub/fake/entity/list", '["a", "b", "c"]', 1, True),
        call.async_publish("pub/fake/entity/bool", "false", 1, True),
    ]

    mqtt_mock.async_publish.assert_has_calls(calls, any_order=True)
    assert mqtt_mock.async_publish.called


async def test_state_changed_event_include_domain(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on included domain works as expected."""
    base_topic = "pub"

    incl = {"domains": ["fake"]}
    excl = {}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake2.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_include_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on included entity works as expected."""
    base_topic = "pub"

    incl = {"entities": ["fake.entity"]}
    excl = {}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_exclude_domain(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on excluded domain works as expected."""
    base_topic = "pub"

    incl = {}
    excl = {"domains": ["fake2"]}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake2.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_exclude_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on excluded entity works as expected."""
    base_topic = "pub"

    incl = {}
    excl = {"entities": ["fake.entity2"]}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_exclude_domain_include_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test filtering with excluded domain and included entity."""
    base_topic = "pub"

    incl = {"entities": ["fake.entity"]}
    excl = {"domains": ["fake"]}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_include_domain_exclude_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test filtering with included domain and excluded entity."""
    base_topic = "pub"

    incl = {"domains": ["fake"]}
    excl = {"entities": ["fake.entity2"]}

    # Add the statestream component for publishing state updates
    # Set the filter to allow fake.* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_include_globs(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on included glob works as expected."""
    base_topic = "pub"

    incl = {"entity_globs": ["*.included_*"]}
    excl = {}

    # Add the statestream component for publishing state updates
    # Set the filter to allow *.included_* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity with included glob
    mock_state_change_event(hass, State("fake2.included_entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake2/included_entity/state
    mqtt_mock.async_publish.assert_called_with(
        "pub/fake2/included_entity/state", "on", 1, True
    )
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake2.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_exclude_globs(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test that filtering on excluded globs works as expected."""
    base_topic = "pub"

    incl = {}
    excl = {"entity_globs": ["*.excluded_*"]}

    # Add the statestream component for publishing state updates
    # Set the filter to allow *.excluded_* items
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included by glob
    mock_state_change_event(hass, State("fake.excluded_entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_exclude_domain_globs_include_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test filtering with excluded domain and glob and included entity."""
    base_topic = "pub"

    incl = {"entities": ["fake.entity"]}
    excl = {"domains": ["fake"], "entity_globs": ["*.excluded_*"]}

    # Add the statestream component for publishing state updates
    # Set the filter to exclude with include filter
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that doesn't match any filters
    mock_state_change_event(hass, State("fake2.included_entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with(
        "pub/fake2/included_entity/state", "on", 1, True
    )
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included by domain
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included by glob
    mock_state_change_event(hass, State("fake.excluded_entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_state_changed_event_include_domain_globs_exclude_entity(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test filtering with included domain and glob and excluded entity."""
    base_topic = "pub"

    incl = {"domains": ["fake"], "entity_globs": ["*.included_*"]}
    excl = {"entities": ["fake.entity2"]}

    # Add the statestream component for publishing state updates
    # Set the filter to include with exclude filter
    assert await add_statestream(
        hass, base_topic=base_topic, publish_include=incl, publish_exclude=excl
    )
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_statestream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity included by domain
    mock_state_change_event(hass, State("fake.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with("pub/fake/entity/state", "on", 1, True)
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity included by glob
    mock_state_change_event(hass, State("fake.included_entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Make sure 'on' was published to pub/fake/entity/state
    mqtt_mock.async_publish.assert_called_with(
        "pub/fake/included_entity/state", "on", 1, True
    )
    assert mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that shouldn't be included
    mock_state_change_event(hass, State("fake.entity2", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called

    mqtt_mock.async_publish.reset_mock()
    # Set a state of an entity that doesn't match any filters
    mock_state_change_event(hass, State("fake2.entity", "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called

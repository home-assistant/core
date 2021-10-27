"""The tests for the MQTT statestream component."""
from unittest.mock import ANY, call

import homeassistant.components.mqtt_statestream as statestream
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import mock_state_change_event


async def add_statestream(
    hass,
    base_topic=None,
    publish_attributes=None,
    publish_timestamps=None,
    publish_include=None,
    publish_exclude=None,
):
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


async def test_fails_with_no_base(hass, mqtt_mock):
    """Setup should fail if no base_topic is set."""
    assert await add_statestream(hass) is False


async def test_setup_succeeds_without_attributes(hass, mqtt_mock):
    """Test the success of the setup with a valid base_topic."""
    assert await add_statestream(hass, base_topic="pub")


async def test_setup_succeeds_with_attributes(hass, mqtt_mock):
    """Test setup with a valid base_topic and publish_attributes."""
    assert await add_statestream(hass, base_topic="pub", publish_attributes=True)


async def test_state_changed_event_sends_message(hass, mqtt_mock):
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


async def test_state_changed_event_sends_message_and_timestamp(hass, mqtt_mock):
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


async def test_state_changed_attr_sends_message(hass, mqtt_mock):
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


async def test_state_changed_event_include_domain(hass, mqtt_mock):
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


async def test_state_changed_event_include_entity(hass, mqtt_mock):
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


async def test_state_changed_event_exclude_domain(hass, mqtt_mock):
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


async def test_state_changed_event_exclude_entity(hass, mqtt_mock):
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


async def test_state_changed_event_exclude_domain_include_entity(hass, mqtt_mock):
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


async def test_state_changed_event_include_domain_exclude_entity(hass, mqtt_mock):
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


async def test_state_changed_event_include_globs(hass, mqtt_mock):
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


async def test_state_changed_event_exclude_globs(hass, mqtt_mock):
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


async def test_state_changed_event_exclude_domain_globs_include_entity(hass, mqtt_mock):
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


async def test_state_changed_event_include_domain_globs_exclude_entity(hass, mqtt_mock):
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

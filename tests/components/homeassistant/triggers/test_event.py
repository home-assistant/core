"""The tests for the Event automation."""

import logging

import attr
import pytest

from homeassistant.components import automation
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, script, trigger
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_component


@pytest.fixture
def context_with_user() -> Context:
    """Create a context with default user_id."""
    return Context(user_id="test_user_id")


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")


async def test_if_fires_on_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[0].data["id"] == 0


async def test_if_fires_on_templated_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {"event_type": "test_event"},
                "trigger": {"platform": "event", "event_type": "{{event_type}}"},
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_on_multiple_events(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": ["test_event", "test2_event"],
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    hass.bus.async_fire("test2_event", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[0].context.parent_id == context.id
    assert service_calls[1].context.parent_id == context.id


async def test_if_fires_on_event_extra_data(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test the firing of events still matches with event data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            }
        },
    )
    hass.bus.async_fire(
        "test_event", {"extra_key": "extra_data"}, context=context_with_user
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_if_fires_on_event_with_data_and_context(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test the firing of events with data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {
                        "some_attr": "some_value",
                        "second_attr": "second_value",
                    },
                    "context": {"user_id": context_with_user.user_id},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value", "second_attr": "second_value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1  # No new call

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value", "second_attr": "second_value"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_event_with_templated_data_and_context(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test the firing of events with templated data and context."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {
                    "attr_1_val": "milk",
                    "attr_2_val": "beer",
                    "user_id": context_with_user.user_id,
                },
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {
                        "attr_1": "{{attr_1_val}}",
                        "attr_2": "{{attr_2_val}}",
                    },
                    "context": {"user_id": "{{user_id}}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value", "attr_2": "beer"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1  # No new call

    hass.bus.async_fire(
        "test_event",
        {"attr_1": "milk", "another": "value", "attr_2": "beer"},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_event_with_empty_data_and_context_config(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test the firing of events with empty data and context config.

    The frontend automation editor can produce configurations with an
    empty dict for event_data instead of no key.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                    "context": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event",
        {"some_attr": "some_value", "another": "value"},
        context=context_with_user,
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_event_with_nested_data(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events with nested data.

    This test exercises the slow path of using vol.Schema to validate
    matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"parent_attr": {"some_attr": "some_value"}},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "test_event", {"parent_attr": {"some_attr": "some_value", "another": "value"}}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_event_with_empty_data(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events with empty data.

    This test exercises the fast path to validate matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    hass.bus.async_fire("test_event", {"any_attr": {}})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_sample_zha_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events with a sample zha event.

    This test exercises the fast path to validate matching event data.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "zha_event",
                    "event_data": {
                        "device_ieee": "00:15:8d:00:02:93:04:11",
                        "command": "attribute_updated",
                        "args": {
                            "attribute_id": 0,
                            "attribute_name": "on_off",
                            "value": True,
                        },
                    },
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire(
        "zha_event",
        {
            "device_ieee": "00:15:8d:00:02:93:04:11",
            "unique_id": "00:15:8d:00:02:93:04:11:1:0x0006",
            "endpoint_id": 1,
            "cluster_id": 6,
            "command": "attribute_updated",
            "args": {"attribute_id": 0, "attribute_name": "on_off", "value": True},
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.bus.async_fire(
        "zha_event",
        {
            "device_ieee": "00:15:8d:00:02:93:04:11",
            "unique_id": "00:15:8d:00:02:93:04:11:1:0x0006",
            "endpoint_id": 1,
            "cluster_id": 6,
            "command": "attribute_updated",
            "args": {"attribute_id": 0, "attribute_name": "on_off", "value": False},
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_not_fires_if_event_data_not_matches(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test firing of event if no data match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"some_attr": "some_value"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"some_attr": "some_other_value"})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_if_not_fires_if_event_context_not_matches(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test firing of event if no context match."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "context": {"user_id": "some_user"},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {}, context=context_with_user)
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_if_fires_on_multiple_user_ids(
    hass: HomeAssistant, service_calls: list[ServiceCall], context_with_user: Context
) -> None:
    """Test the firing of event when the trigger has multiple user ids.

    This test exercises the slow path of using vol.Schema to validate
    matching event context.
    """
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {},
                    "context": {"user_id": [context_with_user.user_id, "another id"]},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {}, context=context_with_user)
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_event_data_with_list(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the (non)firing of event when the data schema has lists."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"some_attr": [1, 2]},
                    "context": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"some_attr": [1, 2]})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match a single value
    hass.bus.async_fire("test_event", {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match a containing list
    hass.bus.async_fire("test_event", {"some_attr": [1, 2, 3]})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match if property doesn't exist at all
    hass.bus.async_fire("test_event", {"other_attr": [1, 2]})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_event_data_with_list_nested(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the (non)firing of event when the data schema has nested lists."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "event_data": {"service_data": {"some_attr": [1, 2]}},
                    "context": {},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event", {"service_data": {"some_attr": [1, 2]}})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match a single value
    hass.bus.async_fire("test_event", {"service_data": {"some_attr": 1}})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match a containing list
    hass.bus.async_fire("test_event", {"service_data": {"some_attr": [1, 2, 3]}})
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    # don't match if property doesn't exist at all
    hass.bus.async_fire("test_event", {"service_data": {"other_attr": [1, 2]}})
    await hass.async_block_till_done()
    assert len(service_calls) == 1


@pytest.mark.parametrize(
    "event_type", ["state_reported", ["test_event", "state_reported"]]
)
async def test_state_reported_event(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
    event_type: str | list[str],
) -> None:
    """Test triggering on state reported event."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": event_type},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Can't "
        "listen to state_reported in event trigger at 'event_type'. Got None"
        in caplog.text
    )


async def test_templated_state_reported_event(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test triggering on state reported event."""
    context = Context()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger_variables": {"event_type": "state_reported"},
                "trigger": {"platform": "event", "event_type": "{{event_type}}"},
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event", context=context)
    await hass.async_block_till_done()
    assert len(service_calls) == 0
    assert (
        "Got error 'Can't listen to state_reported in event trigger' "
        "when setting up triggers for automation 0" in caplog.text
    )


COMPOSITE_ID = "composite00000000000000000000ab"


@pytest.fixture
def split_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> tuple[dr.DeviceEntry, dr.DeviceEntry]:
    """Create two devices which are splits of a pre-migration composite device."""
    entry_1 = MockConfigEntry(domain="itg1")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="itg2")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        identifiers={("itg1", "1")},
        name="Split device 1",
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("itg2", "1")},
        name="Split device 2",
    )
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=COMPOSITE_ID
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=COMPOSITE_ID
    )
    return device_registry._devices[device_1.id], device_registry._devices[device_2.id]


_EVENT_TRIGGER = {
    "platform": "event",
    "event_type": "my_event",
    "event_data": {"device_id": COMPOSITE_ID},
}


def _expected_composite_warning(
    device_1: dr.DeviceEntry, device_2: dr.DeviceEntry
) -> str:
    """Return the exact warning the event validator logs for a composite device id."""
    return (
        f"Event trigger filters on device '{COMPOSITE_ID}', which was split into one "
        "device per integration and no longer exists, so the trigger can no longer fire. "
        "Update the automation, script or template entity to filter on one of these "
        "devices instead: "
        f"Split device 1 ({device_1.id}) from the itg1 integration, "
        f"Split device 2 ({device_2.id}) from the itg2 integration.\n"
        "The affected trigger is configured as:\n"
        "platform: event\n"
        "event_type: my_event\n"
        "event_data:\n"
        f"  device_id: {COMPOSITE_ID}\n"
    )


async def test_composite_device_id_logs_warning(
    hass: HomeAssistant,
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a composite event_data.device_id filter logs the full warning."""
    with caplog.at_level(logging.WARNING):
        await trigger.async_validate_trigger_config(hass, [_EVENT_TRIGGER])
    assert caplog.messages == [_expected_composite_warning(*split_devices)]


async def test_live_device_id_no_warning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a live event_data.device_id filter does not warn."""
    entry = MockConfigEntry(domain="itg")
    entry.add_to_hass(hass)
    live_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("itg", "1")}
    )
    with caplog.at_level(logging.WARNING):
        await trigger.async_validate_trigger_config(
            hass,
            [
                {
                    "platform": "event",
                    "event_type": "my_event",
                    "event_data": {"device_id": live_device.id},
                }
            ],
        )
    assert caplog.messages == []


async def test_wait_for_trigger_composite_device_id_logs_warning(
    hass: HomeAssistant,
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a composite device_id in a wait_for_trigger event trigger warns too."""
    with caplog.at_level(logging.WARNING):
        await script.async_validate_actions_config(
            hass, [{"wait_for_trigger": [_EVENT_TRIGGER]}]
        )
    assert caplog.messages == [_expected_composite_warning(*split_devices)]

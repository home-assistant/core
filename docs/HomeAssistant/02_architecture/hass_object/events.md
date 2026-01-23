---
title: "Events"
---

The core of Home Assistant is driven by events. That means that if you want to respond to something happening, you'll have to respond to events. Most of the times you won't interact directly with the event system but use one of the [event listener helpers][helpers].

The event system is very flexible. There are no limitations on the event type, as long as it's a string. Each event can contain data. The data is a dictionary that can contain any data as long as it's JSON serializable. This means that you can use number, string, dictionary and list.

[List of events that Home Assistant fires.][object]

## Firing events

To fire an event, you have to interact with the event bus. The event bus is available on the Home Assistant instance as `hass.bus`. Please be mindful of the data structure as documented on our [Data Science portal](https://data.home-assistant.io/docs/events/#database-table).

Example component that will fire an event when loaded. Note that custom event names are prefixed with the component name.

```python
DOMAIN = "example_component"


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    # Fire event example_component_my_cool_event with event data answer=42
    hass.bus.fire("example_component_my_cool_event", {"answer": 42})

    # Return successful setup
    return True
```

## Listening to events

Most of the times you'll not be firing events but instead listen to events. For example, the state change of an entity is broadcasted as an event.

```python
DOMAIN = "example_component"


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    count = 0

    # Listener to handle fired events
    def handle_event(event):
        nonlocal count
        count += 1
        print(f"Answer {count} is: {event.data.get('answer')}")

    # Listen for when example_component_my_cool_event is fired
    hass.bus.listen("example_component_my_cool_event", handle_event)

    # Return successful setup
    return True
```

### Helpers

Home Assistant comes with a lot of bundled helpers to listen to specific types of event. There are helpers to track a point in time, to track a time interval, a state change or the sun set. [See available methods.][helpers]

[helpers]: https://developers.home-assistant.io/docs/integration_listen_events#available-event-helpers
[object]: https://www.home-assistant.io/docs/configuration/events/

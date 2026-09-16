@pytest.mark.parametrize("node_fixture", ["mock_generic_switch"])
async def test_generic_switch_unknown_event(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test an event id that is not a switch event is ignored."""
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=1,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )
    state = hass.states.get("event.mock_generic_switch_button")
    last_event = state.state

    # an event id outside of the switch event id space
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=7,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )

    state = hass.states.get("event.mock_generic_switch_button")
    assert state.state == last_event
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"

    # an event id that another cluster on the same endpoint uses, here the
    # door lock LockOperation event, which shares its id with a long press
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=257,
            event_id=2,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )

    state = hass.states.get("event.mock_generic_switch_button")
    assert state.state == last_event
    assert state.attributes[ATTR_EVENT_TYPE] == "initial_press"


@pytest.mark.parametrize("node_fixture", ["mock_doorbell"])
async def test_doorbell_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test event entity for a Doorbell node."""
    state = hass.states.get("event.mock_doorbell_doorbell")
    assert state
    assert state.state == "unknown"
    # check event_types from featuremap 14 (0b1110): 'initial_press' is
    # remapped to the standard 'ring' event type for the doorbell device class
    assert state.attributes[ATTR_EVENT_TYPES] == [
        "ring",
        "short_release",
        "long_press",
        "long_release",
    ]
    # trigger firing a new (initial press) event from the device
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_EVENT,
        MatterNodeEvent(
            node_id=matter_node.node_id,
            endpoint_id=1,
            cluster_id=59,
            event_id=1,
            event_number=0,
            priority=1,
            timestamp=0,
            timestamp_type=0,
            data=None,
        ),
    )
    state = hass.states.get("event.mock_doorbell_doorbell")
    assert state.attributes[ATTR_EVENT_TYPE] == "ring"
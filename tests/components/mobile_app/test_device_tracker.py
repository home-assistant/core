"""Test mobile app device tracker."""


async def test_sending_location(hass, create_registrations, webhook_client):
    """Test sending a location via a webhook."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {
                "gps": [10, 20],
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "location_name": "bar",
            },
        },
    )

    assert resp.status == 200
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.name == "Test 1"
    assert state.state == "bar"
    assert state.attributes["source_type"] == "gps"
    assert state.attributes["latitude"] == 10
    assert state.attributes["longitude"] == 20
    assert state.attributes["gps_accuracy"] == 30
    assert state.attributes["battery_level"] == 40
    assert state.attributes["altitude"] == 50
    assert state.attributes["course"] == 60
    assert state.attributes["speed"] == 70
    assert state.attributes["vertical_accuracy"] == 80

    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {
                "gps": [1, 2],
                "gps_accuracy": 3,
                "battery": 4,
                "altitude": 5,
                "course": 6,
                "speed": 7,
                "vertical_accuracy": 8,
            },
        },
    )

    assert resp.status == 200
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_1_2")
    assert state is not None
    assert state.state == "not_home"
    assert state.attributes["source_type"] == "gps"
    assert state.attributes["latitude"] == 1
    assert state.attributes["longitude"] == 2
    assert state.attributes["gps_accuracy"] == 3
    assert state.attributes["battery_level"] == 4
    assert state.attributes["altitude"] == 5
    assert state.attributes["course"] == 6
    assert state.attributes["speed"] == 7
    assert state.attributes["vertical_accuracy"] == 8


async def test_restoring_location(hass, create_registrations, webhook_client):
    """Test sending a location via a webhook."""
    resp = await webhook_client.post(
        "/api/webhook/{}".format(create_registrations[1]["webhook_id"]),
        json={
            "type": "update_location",
            "data": {
                "gps": [10, 20],
                "gps_accuracy": 30,
                "battery": 40,
                "altitude": 50,
                "course": 60,
                "speed": 70,
                "vertical_accuracy": 80,
                "location_name": "bar",
            },
        },
    )

    assert resp.status == 200
    await hass.async_block_till_done()
    state_1 = hass.states.get("device_tracker.test_1_2")
    assert state_1 is not None

    config_entry = hass.config_entries.async_entries("mobile_app")[1]

    # mobile app doesn't support unloading, so we just reload device tracker
    await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")
    await hass.config_entries.async_forward_entry_setup(config_entry, "device_tracker")
    await hass.async_block_till_done()

    state_2 = hass.states.get("device_tracker.test_1_2")
    assert state_2 is not None

    assert state_1 is not state_2
    assert state_2.name == "Test 1"
    assert state_2.attributes["source_type"] == "gps"
    assert state_2.attributes["latitude"] == 10
    assert state_2.attributes["longitude"] == 20
    assert state_2.attributes["gps_accuracy"] == 30
    assert state_2.attributes["battery_level"] == 40
    assert state_2.attributes["altitude"] == 50
    assert state_2.attributes["course"] == 60
    assert state_2.attributes["speed"] == 70
    assert state_2.attributes["vertical_accuracy"] == 80

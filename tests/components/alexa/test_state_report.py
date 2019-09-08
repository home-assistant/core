"""Test report state."""
from homeassistant.components.alexa import state_report
from . import TEST_URL, DEFAULT_CONFIG


async def test_report_state(hass, aioclient_mock):
    """Test proactive state reports."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_enable_proactive_mode(hass, DEFAULT_CONFIG)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa"
    assert call_json["event"]["header"]["name"] == "ChangeReport"
    assert (
        call_json["event"]["payload"]["change"]["properties"][0]["value"]
        == "NOT_DETECTED"
    )
    assert call_json["event"]["endpoint"]["endpointId"] == "binary_sensor#test_contact"


async def test_send_add_or_update_message(hass, aioclient_mock):
    """Test sending an AddOrUpdateReport message."""
    aioclient_mock.post(TEST_URL, text="")

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_send_add_or_update_message(
        hass, DEFAULT_CONFIG, ["binary_sensor.test_contact"]
    )

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa.Discovery"
    assert call_json["event"]["header"]["name"] == "AddOrUpdateReport"
    assert len(call_json["event"]["payload"]["endpoints"]) == 1
    assert (
        call_json["event"]["payload"]["endpoints"][0]["endpointId"]
        == "binary_sensor#test_contact"
    )


async def test_send_delete_message(hass, aioclient_mock):
    """Test sending an AddOrUpdateReport message."""
    aioclient_mock.post(TEST_URL, json={"data": "is irrelevant"})

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_send_delete_message(
        hass, DEFAULT_CONFIG, ["binary_sensor.test_contact"]
    )

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa.Discovery"
    assert call_json["event"]["header"]["name"] == "DeleteReport"
    assert len(call_json["event"]["payload"]["endpoints"]) == 1
    assert (
        call_json["event"]["payload"]["endpoints"][0]["endpointId"]
        == "binary_sensor#test_contact"
    )

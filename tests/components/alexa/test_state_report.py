"""Test report state."""
from homeassistant.components.alexa import state_report
from . import TEST_URL, DEFAULT_CONFIG


async def test_report_state(hass, aioclient_mock):
    """Test proactive state reports."""
    aioclient_mock.post(TEST_URL, json={'data': 'is irrelevant'})

    hass.states.async_set(
        'binary_sensor.test_contact',
        'on',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )

    await state_report.async_enable_proactive_mode(hass, DEFAULT_CONFIG)

    hass.states.async_set(
        'binary_sensor.test_contact',
        'off',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["payload"]["change"]["properties"][0]["value"] \
        == "NOT_DETECTED"
    assert call_json["event"]["endpoint"]["endpointId"] \
        == "binary_sensor#test_contact"

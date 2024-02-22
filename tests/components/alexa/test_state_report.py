"""Test report state."""
import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant import core
from homeassistant.components.alexa import errors, state_report
from homeassistant.components.alexa.resources import AlexaGlobalCatalog
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant

from .test_common import TEST_URL, get_default_config

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_report_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test proactive state reports."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

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


async def test_report_state_fail(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test proactive state retries once."""
    aioclient_mock.post(
        TEST_URL,
        text=json.dumps(
            {
                "payload": {
                    "code": "THROTTLING_EXCEPTION",
                    "description": "Request could not be processed due to throttling",
                }
            }
        ),
        status=403,
    )

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    # No retry on errors not related to expired access token
    assert len(aioclient_mock.mock_calls) == 1

    # Check we log the entity id of the failing entity
    assert (
        "Error when sending ChangeReport for binary_sensor.test_contact to Alexa: "
        "THROTTLING_EXCEPTION: Request could not be processed due to throttling"
    ) in caplog.text


async def test_report_state_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test proactive state retries once."""
    aioclient_mock.post(
        TEST_URL,
        exc=aiohttp.ClientError(),
    )

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    # No retry on errors not related to expired access token
    assert len(aioclient_mock.mock_calls) == 1

    # Check we log the entity id of the failing entity
    assert (
        "Timeout sending report to Alexa for binary_sensor.test_contact" in caplog.text
    )


async def test_report_state_retry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test proactive state retries once."""
    aioclient_mock.post(
        TEST_URL,
        text='{"payload":{"code":"INVALID_ACCESS_TOKEN_EXCEPTION","description":""}}',
        status=403,
    )

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 2


async def test_report_state_unsets_authorized_on_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test proactive state unsets authorized on error."""
    aioclient_mock.post(
        TEST_URL,
        text='{"payload":{"code":"INVALID_ACCESS_TOKEN_EXCEPTION","description":""}}',
        status=403,
    )

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    config = get_default_config(hass)
    await state_report.async_enable_proactive_mode(hass, config)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    config._store.set_authorized.assert_not_called()

    # To trigger event listener
    await hass.async_block_till_done()
    config._store.set_authorized.assert_called_once_with(False)


@pytest.mark.parametrize("exc", [errors.NoTokenAvailable, errors.RequireRelink])
async def test_report_state_unsets_authorized_on_access_token_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, exc: Exception
) -> None:
    """Test proactive state unsets authorized on error."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    config = get_default_config(hass)

    await state_report.async_enable_proactive_mode(hass, config)

    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    config._store.set_authorized.assert_not_called()

    with patch.object(config, "async_get_access_token", AsyncMock(side_effect=exc)):
        # To trigger event listener
        await hass.async_block_till_done()
        config._store.set_authorized.assert_called_once_with(False)


async def test_report_state_fan(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test proactive state reports with fan instance."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "fan.test_fan",
        "off",
        {
            "friendly_name": "Test fan",
            "supported_features": 15,
            "oscillating": False,
            "preset_mode": None,
            "preset_modes": ["auto", "smart"],
            "percentage": None,
        },
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "fan.test_fan",
        "on",
        {
            "friendly_name": "Test fan",
            "supported_features": 15,
            "oscillating": True,
            "preset_mode": "smart",
            "preset_modes": ["auto", "smart"],
            "percentage": 90,
        },
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa"
    assert call_json["event"]["header"]["name"] == "ChangeReport"

    change_reports = call_json["event"]["payload"]["change"]["properties"]

    checks = 0
    for report in change_reports:
        if report["name"] == "toggleState":
            assert report["value"] == "ON"
            assert report["instance"] == "fan.oscillating"
            assert report["namespace"] == "Alexa.ToggleController"
            checks += 1
        if report["name"] == "mode":
            assert report["value"] == "preset_mode.smart"
            assert report["instance"] == "fan.preset_mode"
            assert report["namespace"] == "Alexa.ModeController"
            checks += 1
        if report["name"] == "rangeValue":
            assert report["value"] == 90
            assert report["instance"] == "fan.percentage"
            assert report["namespace"] == "Alexa.RangeController"
            checks += 1
    assert checks == 3

    assert call_json["event"]["endpoint"]["endpointId"] == "fan#test_fan"


async def test_report_state_humidifier(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test proactive state reports with humidifier instance."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "humidifier.test_humidifier",
        "off",
        {
            "friendly_name": "Test humidifier",
            "supported_features": 1,
            "mode": None,
            "available_modes": ["auto", "smart"],
        },
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "humidifier.test_humidifier",
        "on",
        {
            "friendly_name": "Test humidifier",
            "supported_features": 1,
            "mode": "smart",
            "available_modes": ["auto", "smart"],
            "humidity": 55,
        },
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa"
    assert call_json["event"]["header"]["name"] == "ChangeReport"

    change_reports = call_json["event"]["payload"]["change"]["properties"]

    checks = 0
    for report in change_reports:
        if report["name"] == "mode":
            assert report["value"] == "mode.smart"
            assert report["instance"] == "humidifier.mode"
            assert report["namespace"] == "Alexa.ModeController"
            checks += 1
        if report["name"] == "rangeValue":
            assert report["value"] == 55
            assert report["instance"] == "humidifier.humidity"
            assert report["namespace"] == "Alexa.RangeController"
            checks += 1
    assert checks == 2

    assert call_json["event"]["endpoint"]["endpointId"] == "humidifier#test_humidifier"


@pytest.mark.parametrize(
    ("domain", "value", "unit", "label"),
    [
        (
            "number",
            50,
            None,
            AlexaGlobalCatalog.SETTING_PRESET,
        ),
        (
            "input_number",
            40,
            UnitOfLength.METERS,
            AlexaGlobalCatalog.UNIT_DISTANCE_METERS,
        ),
        (
            "number",
            20.5,
            UnitOfTemperature.CELSIUS,
            AlexaGlobalCatalog.UNIT_TEMPERATURE_CELSIUS,
        ),
        (
            "input_number",
            40.5,
            UnitOfLength.MILLIMETERS,
            AlexaGlobalCatalog.SETTING_PRESET,
        ),
        (
            "number",
            20.5,
            PERCENTAGE,
            AlexaGlobalCatalog.UNIT_PERCENT,
        ),
    ],
)
async def test_report_state_number(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    domain: str,
    value: float,
    unit: str | None,
    label: AlexaGlobalCatalog,
) -> None:
    """Test proactive state reports with number or input_number instance."""
    aioclient_mock.post(TEST_URL, text="", status=202)
    state = {
        "friendly_name": f"Test {domain}",
        "min": 10,
        "max": 100,
        "step": 0.1,
    }

    if unit:
        state["unit_of_measurement"]: unit

    hass.states.async_set(
        f"{domain}.test_{domain}",
        None,
        state,
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        f"{domain}.test_{domain}",
        value,
        state,
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa"
    assert call_json["event"]["header"]["name"] == "ChangeReport"

    change_reports = call_json["event"]["payload"]["change"]["properties"]

    checks = 0
    for report in change_reports:
        if report["name"] == "connectivity":
            assert report["value"] == {"value": "OK"}
            assert report["namespace"] == "Alexa.EndpointHealth"
            checks += 1
        if report["name"] == "rangeValue":
            assert report["value"] == value
            assert report["instance"] == f"{domain}.value"
            assert report["namespace"] == "Alexa.RangeController"
            checks += 1
    assert checks == 2

    assert call_json["event"]["endpoint"]["endpointId"] == f"{domain}#test_{domain}"


async def test_send_add_or_update_message(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending an AddOrUpdateReport message."""
    aioclient_mock.post(TEST_URL, text="")

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    hass.states.async_set(
        "zwave.bla",
        "wow_such_unsupported",
    )

    entities = [
        "binary_sensor.test_contact",
        "binary_sensor.non_existing",  # Supported, but does not exist
        "zwave.bla",  # Unsupported
    ]
    await state_report.async_send_add_or_update_message(
        hass, get_default_config(hass), entities
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


async def test_send_delete_message(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending an AddOrUpdateReport message."""
    aioclient_mock.post(TEST_URL, json={"data": "is irrelevant"})

    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    await state_report.async_send_delete_message(
        hass, get_default_config(hass), ["binary_sensor.test_contact", "zwave.bla"]
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


async def test_doorbell_event(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test doorbell press reports."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "off",
        {
            "friendly_name": "Test Doorbell Sensor",
            "device_class": "occupancy",
            "linkquality": 42,
        },
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {
            "friendly_name": "Test Doorbell Sensor",
            "device_class": "occupancy",
            "linkquality": 42,
        },
    )

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {
            "friendly_name": "Test Doorbell Sensor",
            "device_class": "occupancy",
            "linkquality": 99,
        },
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa.DoorbellEventSource"
    assert call_json["event"]["header"]["name"] == "DoorbellPress"
    assert call_json["event"]["payload"]["cause"]["type"] == "PHYSICAL_INTERACTION"
    assert call_json["event"]["endpoint"]["endpointId"] == "binary_sensor#test_doorbell"

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "off",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 2


async def test_doorbell_event_from_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test doorbell press reports."""
    aioclient_mock.post(TEST_URL, text="", status=202)

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {
            "friendly_name": "Test Doorbell Sensor",
            "device_class": "occupancy",
        },
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = call[0][2]
    assert call_json["event"]["header"]["namespace"] == "Alexa.DoorbellEventSource"
    assert call_json["event"]["header"]["name"] == "DoorbellPress"
    assert call_json["event"]["payload"]["cause"]["type"] == "PHYSICAL_INTERACTION"
    assert call_json["event"]["endpoint"]["endpointId"] == "binary_sensor#test_doorbell"


async def test_doorbell_event_fail(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test proactive state retries once."""
    aioclient_mock.post(
        TEST_URL,
        text=json.dumps(
            {
                "payload": {
                    "code": "THROTTLING_EXCEPTION",
                    "description": "Request could not be processed due to throttling",
                }
            }
        ),
        status=403,
    )

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "off",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    # No retry on errors not related to expired access token
    assert len(aioclient_mock.mock_calls) == 1

    # Check we log the entity id of the failing entity
    assert (
        "Error when sending DoorbellPress event for binary_sensor.test_doorbell"
        " to Alexa: THROTTLING_EXCEPTION: Request could not be processed"
        " due to throttling"
    ) in caplog.text


async def test_doorbell_event_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test proactive state retries once."""
    aioclient_mock.post(
        TEST_URL,
        exc=aiohttp.ClientError(),
    )

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "off",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    await state_report.async_enable_proactive_mode(hass, get_default_config(hass))

    hass.states.async_set(
        "binary_sensor.test_doorbell",
        "on",
        {"friendly_name": "Test Doorbell Sensor", "device_class": "occupancy"},
    )

    # To trigger event listener
    await hass.async_block_till_done()

    # No retry on errors not related to expired access token
    assert len(aioclient_mock.mock_calls) == 1

    # Check we log the entity id of the failing entity
    assert (
        "Timeout sending report to Alexa for binary_sensor.test_doorbell" in caplog.text
    )


async def test_proactive_mode_filter_states(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test all the cases that filter states."""
    aioclient_mock.post(TEST_URL, text="", status=202)
    config = get_default_config(hass)
    await state_report.async_enable_proactive_mode(hass, config)

    # First state should report
    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()

    # Second one shouldn't
    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )
    assert len(aioclient_mock.mock_calls) == 0

    # hass not running should not report
    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )

    current_state = hass.state
    hass.set_state(core.CoreState.stopping)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    hass.set_state(current_state)
    assert len(aioclient_mock.mock_calls) == 0

    # unsupported entity should not report
    hass.states.async_set(
        "binary_sensor.test_contact",
        "on",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )
    with patch.dict(
        "homeassistant.components.alexa.state_report.ENTITY_ADAPTERS", {}, clear=True
    ):
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 0

    # Not exposed by config should not report
    hass.states.async_set(
        "binary_sensor.test_contact",
        "off",
        {"friendly_name": "Test Contact Sensor", "device_class": "door"},
    )
    with patch.object(config, "should_expose", return_value=False):
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 0

    # Removing an entity
    hass.states.async_remove("binary_sensor.test_contact")
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 0

    # If serializes to same properties, it should not report
    aioclient_mock.post(TEST_URL, text="", status=202)
    with patch(
        "homeassistant.components.alexa.entities.AlexaEntity.serialize_properties",
        return_value=[{"same": "info"}],
    ):
        hass.states.async_set(
            "binary_sensor.same_serialize",
            "off",
            {"friendly_name": "Test Contact Sensor", "device_class": "door"},
        )
        await hass.async_block_till_done()
        hass.states.async_set(
            "binary_sensor.same_serialize",
            "off",
            {"friendly_name": "Test Contact Sensor", "device_class": "door"},
        )

        await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 1

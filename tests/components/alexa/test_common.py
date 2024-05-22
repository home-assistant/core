"""Test helpers for the Alexa integration."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from homeassistant.components.alexa import config, smart_home
from homeassistant.components.alexa.const import CONF_ENDPOINT, CONF_FILTER, CONF_LOCALE
from homeassistant.core import Context, callback
from homeassistant.helpers import entityfilter

from tests.common import async_mock_service

TEST_URL = "https://api.amazonalexa.com/v3/events"
TEST_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
TEST_LOCALE = "en-US"


class MockConfig(smart_home.AlexaConfig):
    """Mock Alexa config."""

    entity_config = {
        "binary_sensor.test_doorbell": {"display_categories": "DOORBELL"},
        "binary_sensor.test_contact_forced": {"display_categories": "CONTACT_SENSOR"},
        "binary_sensor.test_motion_forced": {"display_categories": "MOTION_SENSOR"},
        "binary_sensor.test_motion_camera_event": {"display_categories": "CAMERA"},
        "camera.test": {"display_categories": "CAMERA"},
    }

    def __init__(self, hass):
        """Mock Alexa config."""
        super().__init__(
            hass,
            {
                CONF_ENDPOINT: TEST_URL,
                CONF_FILTER: entityfilter.FILTER_SCHEMA({}),
                CONF_LOCALE: TEST_LOCALE,
            },
        )
        self._store = Mock(spec_set=config.AlexaConfigStore)

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return True

    @callback
    def user_identifier(self):
        """Return an identifier for the user that represents this config."""
        return "mock-user-id"

    @callback
    def async_invalidate_access_token(self):
        """Invalidate access token."""

    async def async_get_access_token(self):
        """Get an access token."""
        return "thisisnotanacesstoken"

    async def async_accept_grant(self, code):
        """Accept a grant."""


def get_default_config(hass):
    """Return a MockConfig instance."""
    return MockConfig(hass)


def get_new_request(namespace, name, endpoint=None):
    """Generate a new API message."""
    raw_msg = {
        "directive": {
            "header": {
                "namespace": namespace,
                "name": name,
                "messageId": str(uuid4()),
                "correlationToken": str(uuid4()),
                "payloadVersion": "3",
            },
            "endpoint": {
                "scope": {"type": "BearerToken", "token": str(uuid4())},
                "endpointId": endpoint,
            },
            "payload": {},
        }
    }

    if not endpoint:
        raw_msg["directive"].pop("endpoint")

    return raw_msg


async def assert_request_calls_service(
    namespace,
    name,
    endpoint,
    service,
    hass,
    response_type="Response",
    payload=None,
    instance=None,
):
    """Assert an API request calls a hass service."""
    context = Context()
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request["directive"]["payload"] = payload
    if instance:
        request["directive"]["header"]["instance"] = instance

    domain, service_name = service.split(".")
    calls = async_mock_service(hass, domain, service_name)

    msg = await smart_home.async_handle_message(
        hass, get_default_config(hass), request, context
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert "event" in msg
    assert call.data["entity_id"] == endpoint.replace("#", ".")
    assert msg["event"]["header"]["name"] == response_type
    assert call.context == context

    return call, msg


async def assert_request_fails(
    namespace, name, endpoint, service_not_called, hass, payload=None, instance=None
):
    """Assert an API request returns an ErrorResponse."""
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request["directive"]["payload"] = payload
    if instance:
        request["directive"]["header"]["instance"] = instance

    domain, service_name = service_not_called.split(".")
    call = async_mock_service(hass, domain, service_name)

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()

    assert not call
    assert "event" in msg
    assert msg["event"]["header"]["name"] == "ErrorResponse"

    return msg


async def assert_power_controller_works(
    endpoint, on_service, off_service, hass, timestamp
):
    """Assert PowerController API requests work."""
    _, response = await assert_request_calls_service(
        "Alexa.PowerController", "TurnOn", endpoint, on_service, hass
    )
    for context_property in response["context"]["properties"]:
        assert context_property["timeOfSample"] == timestamp

    _, response = await assert_request_calls_service(
        "Alexa.PowerController", "TurnOff", endpoint, off_service, hass
    )
    for context_property in response["context"]["properties"]:
        assert context_property["timeOfSample"] == timestamp


async def assert_scene_controller_works(
    endpoint, activate_service, deactivate_service, hass, timestamp
):
    """Assert SceneController API requests work."""
    _, response = await assert_request_calls_service(
        "Alexa.SceneController",
        "Activate",
        endpoint,
        activate_service,
        hass,
        response_type="ActivationStarted",
    )
    assert response["event"]["payload"]["cause"]["type"] == "VOICE_INTERACTION"
    assert response["event"]["payload"]["timestamp"] == timestamp
    if deactivate_service:
        _, response = await assert_request_calls_service(
            "Alexa.SceneController",
            "Deactivate",
            endpoint,
            deactivate_service,
            hass,
            response_type="DeactivationStarted",
        )
        cause_type = response["event"]["payload"]["cause"]["type"]
        assert cause_type == "VOICE_INTERACTION"
        assert response["event"]["payload"]["timestamp"] == timestamp


async def reported_properties(hass, endpoint, return_full_response=False):
    """Use ReportState to get properties and return them.

    The result is a ReportedProperties instance, which has methods to make
    assertions about the properties.
    """
    request = get_new_request("Alexa", "ReportState", endpoint)
    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    await hass.async_block_till_done()
    if return_full_response:
        return msg
    return ReportedProperties(msg["context"]["properties"])


class ReportedProperties:
    """Class to help assert reported properties."""

    def __init__(self, properties):
        """Initialize class."""
        self.properties = properties

    def assert_not_has_property(self, namespace, name):
        """Assert a property does not exist."""
        for prop in self.properties:
            if prop["namespace"] == namespace and prop["name"] == name:
                pytest.fail(f"Property {namespace}:{name} exists")

    def assert_equal(self, namespace, name, value):
        """Assert a property is equal to a given value."""
        prop_set = None
        prop_count = 0
        for prop in self.properties:
            if prop["namespace"] == namespace and prop["name"] == name:
                assert prop["value"] == value
                prop_set = prop
                prop_count += 1

        if prop_count > 1:
            pytest.fail(
                f"property {namespace}:{name} more than once in {self.properties!r}"
            )

        if prop_set:
            return prop_set

        pytest.fail(f"property {namespace}:{name} not in {self.properties!r}")

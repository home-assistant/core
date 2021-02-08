"""Tests for the Alexa integration."""
from uuid import uuid4

from homeassistant.components.alexa import config, smart_home
from homeassistant.core import Context, callback

from tests.common import async_mock_service

TEST_URL = "https://api.amazonalexa.com/v3/events"
TEST_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
TEST_LOCALE = "en-US"


class MockConfig(config.AbstractConfig):
    """Mock Alexa config."""

    entity_config = {
        "binary_sensor.test_doorbell": {"display_categories": "DOORBELL"},
        "binary_sensor.test_contact_forced": {"display_categories": "CONTACT_SENSOR"},
        "binary_sensor.test_motion_forced": {"display_categories": "MOTION_SENSOR"},
        "binary_sensor.test_motion_camera_event": {"display_categories": "CAMERA"},
        "camera.test": {"display_categories": "CAMERA"},
    }

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return True

    @property
    def endpoint(self):
        """Endpoint for report state."""
        return TEST_URL

    @property
    def locale(self):
        """Return config locale."""
        return TEST_LOCALE

    @callback
    def user_identifier(self):
        """Return an identifier for the user that represents this config."""
        return "mock-user-id"

    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        return True

    async def async_get_access_token(self):
        """Get an access token."""
        return "thisisnotanacesstoken"

    async def async_accept_grant(self, code):
        """Accept a grant."""


DEFAULT_CONFIG = MockConfig(None)


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

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request, context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert "event" in msg
    assert call.data["entity_id"] == endpoint.replace("#", ".")
    assert msg["event"]["header"]["name"] == response_type
    assert call.context == context

    return call, msg


async def assert_request_fails(
    namespace, name, endpoint, service_not_called, hass, payload=None
):
    """Assert an API request returns an ErrorResponse."""
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request["directive"]["payload"] = payload

    domain, service_name = service_not_called.split(".")
    call = async_mock_service(hass, domain, service_name)

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert not call
    assert "event" in msg
    assert msg["event"]["header"]["name"] == "ErrorResponse"

    return msg


async def assert_power_controller_works(endpoint, on_service, off_service, hass):
    """Assert PowerController API requests work."""
    await assert_request_calls_service(
        "Alexa.PowerController", "TurnOn", endpoint, on_service, hass
    )

    await assert_request_calls_service(
        "Alexa.PowerController", "TurnOff", endpoint, off_service, hass
    )


async def assert_scene_controller_works(
    endpoint, activate_service, deactivate_service, hass
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
    assert "timestamp" in response["event"]["payload"]

    if deactivate_service:
        await assert_request_calls_service(
            "Alexa.SceneController",
            "Deactivate",
            endpoint,
            deactivate_service,
            hass,
            response_type="DeactivationStarted",
        )
        cause_type = response["event"]["payload"]["cause"]["type"]
        assert cause_type == "VOICE_INTERACTION"
        assert "timestamp" in response["event"]["payload"]


async def reported_properties(hass, endpoint):
    """Use ReportState to get properties and return them.

    The result is a ReportedProperties instance, which has methods to make
    assertions about the properties.
    """
    request = get_new_request("Alexa", "ReportState", endpoint)
    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()
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
                assert False, "Property %s:%s exists"

    def assert_equal(self, namespace, name, value):
        """Assert a property is equal to a given value."""
        for prop in self.properties:
            if prop["namespace"] == namespace and prop["name"] == name:
                assert prop["value"] == value
                return prop

        assert False, f"property {namespace}:{name} not in {self.properties!r}"

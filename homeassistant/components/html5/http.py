"""HTTP views for the HTML5 integration."""

from contextlib import suppress
from http import HTTPStatus
import logging
from typing import Any, cast
import warnings

from aiohttp import web
from aiohttp.hdrs import AUTHORIZATION
import jwt
from jwt.warnings import InsecureKeyLengthWarning
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.notify import ATTR_DATA, ATTR_TARGET
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.json import save_json
from homeassistant.util import ensure_unique_string

from .const import ATTR_ACTION, ATTR_ENDPOINT, ATTR_SUBSCRIPTION, ATTR_TAG, DOMAIN
from .entity import Registration
from .issue import deprecated_event_bus

_LOGGER = logging.getLogger(__name__)


ATTR_TYPE = "type"
ATTR_BROWSER = "browser"
ATTR_KEYS = "keys"
ATTR_AUTH = "auth"
ATTR_P256DH = "p256dh"
ATTR_EXPIRATIONTIME = "expirationTime"
NOTIFY_CALLBACK_EVENT = "html5_notification"


KEYS_SCHEMA = vol.All(
    dict,
    vol.Schema(
        {
            vol.Required(ATTR_AUTH): cv.string,
            vol.Required(ATTR_P256DH): cv.string,
        }
    ),
)

SUBSCRIPTION_SCHEMA = vol.All(
    dict,
    vol.Schema(
        {
            vol.Required(ATTR_ENDPOINT): vol.Url(),
            vol.Required(ATTR_KEYS): KEYS_SCHEMA,
            vol.Optional(ATTR_EXPIRATIONTIME): vol.Any(None, cv.positive_int),
        }
    ),
)

REGISTER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SUBSCRIPTION): SUBSCRIPTION_SCHEMA,
        vol.Required(ATTR_BROWSER): vol.In(["chrome", "firefox"]),
        vol.Optional(ATTR_NAME): cv.string,
    }
)

CALLBACK_EVENT_PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TAG): cv.string,
        vol.Required(ATTR_TYPE): vol.In(["received", "clicked", "closed"]),
        vol.Required(ATTR_TARGET): cv.string,
        vol.Optional(ATTR_ACTION): cv.string,
        vol.Optional(ATTR_DATA): dict,
    }
)


@callback
def async_register_http_views(
    hass: HomeAssistant, json_path: str, registrations: dict[str, Registration]
) -> None:
    """Register the http views."""

    hass.http.register_view(HTML5PushRegistrationView(registrations, json_path))
    hass.http.register_view(HTML5PushCallbackView(registrations))


class HTML5PushRegistrationView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    url = "/api/notify.html5"
    name = "api:notify.html5"

    def __init__(self, registrations: dict[str, Registration], json_path: str) -> None:
        """Init HTML5PushRegistrationView."""
        self.registrations = registrations
        self.json_path = json_path

    async def post(self, request: web.Request) -> web.Response:
        """Accept the POST request for push registrations from a browser."""

        try:
            data: Registration = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)
        try:
            data = cast(Registration, REGISTER_SCHEMA(data))
        except vol.Invalid as ex:
            return self.json_message(humanize_error(data, ex), HTTPStatus.BAD_REQUEST)

        devname = data.get(ATTR_NAME)
        data.pop(ATTR_NAME, None)

        name = self.find_registration_name(data, devname)
        previous_registration = self.registrations.get(name)

        self.registrations[name] = data
        hass = request.app[KEY_HASS]

        try:
            await hass.async_add_executor_job(
                save_json, self.json_path, self.registrations
            )
        except HomeAssistantError:
            if previous_registration is not None:
                self.registrations[name] = previous_registration
            else:
                self.registrations.pop(name)

            return self.json_message(
                "Error saving registration.", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self.json_message("Push notification subscriber registered.")

    def find_registration_name(
        self,
        data: Registration,
        suggested: str | None = None,
    ):
        """Find a registration name matching data or generate a unique one."""
        endpoint = data["subscription"]["endpoint"]
        for key, registration in self.registrations.items():
            subscription = registration["subscription"]
            if subscription.get(ATTR_ENDPOINT) == endpoint:
                return key
        return ensure_unique_string(suggested or "unnamed device", self.registrations)

    async def delete(self, request: web.Request):
        """Delete a registration."""
        try:
            data: dict[str, Any] = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        subscription: dict[str, Any] = data[ATTR_SUBSCRIPTION]

        found = None

        for key, registration in self.registrations.items():
            if registration["subscription"] == subscription:
                found = key
                break

        if not found:
            # If not found, unregistering was already done. Return 200
            return self.json_message("Registration not found.")

        reg = self.registrations.pop(found)
        hass = request.app[KEY_HASS]

        try:
            await hass.async_add_executor_job(
                save_json, self.json_path, self.registrations
            )
        except HomeAssistantError:
            self.registrations[found] = reg
            return self.json_message(
                "Error saving registration.", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self.json_message("Push notification subscriber unregistered.")


class HTML5PushCallbackView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    requires_auth = False
    url = "/api/notify.html5/callback"
    name = "api:notify.html5/callback"

    def __init__(self, registrations: dict[str, Registration]) -> None:
        """Init HTML5PushCallbackView."""
        self.registrations = registrations

    def decode_jwt(self, token: str) -> web.Response | dict[str, Any]:
        """Find the registration that signed this JWT and return it."""

        # 1.  Check claims w/o verifying to see if a target is in there.
        # 2.  If target in claims, attempt to verify against the given name.
        # 2a. If decode is successful, return the payload.
        # 2b. If decode is unsuccessful, return a 401.

        target_check: dict[str, Any] = jwt.decode(
            token, algorithms=["ES256", "HS256"], options={"verify_signature": False}
        )
        if target_check.get(ATTR_TARGET) in self.registrations:
            possible_target = self.registrations[target_check[ATTR_TARGET]]
            key = possible_target["subscription"]["keys"]["auth"]
            with (
                suppress(jwt.exceptions.DecodeError, jwt.exceptions.InvalidKeyError),
                warnings.catch_warnings(),
            ):
                warnings.simplefilter("ignore", InsecureKeyLengthWarning)
                return jwt.decode(token, key, algorithms=["ES256", "HS256"])

        return self.json_message(
            "No target found in JWT", status_code=HTTPStatus.UNAUTHORIZED
        )

    # The following is based on code from Auth0
    # https://auth0.com/docs/quickstart/backend/python
    def check_authorization_header(
        self, request: web.Request
    ) -> web.Response | dict[str, Any]:
        """Check the authorization header."""
        if not (auth := request.headers.get(AUTHORIZATION)):
            return self.json_message(
                "Authorization header is expected", status_code=HTTPStatus.UNAUTHORIZED
            )

        parts = auth.split()

        if parts[0].lower() != "bearer":
            return self.json_message(
                "Authorization header must start with Bearer",
                status_code=HTTPStatus.UNAUTHORIZED,
            )
        if len(parts) != 2:
            return self.json_message(
                "Authorization header must be Bearer token",
                status_code=HTTPStatus.UNAUTHORIZED,
            )

        token = parts[1]
        try:
            payload = self.decode_jwt(token)
        except jwt.exceptions.InvalidTokenError:
            return self.json_message(
                "token is invalid", status_code=HTTPStatus.UNAUTHORIZED
            )
        return payload

    async def post(self, request: web.Request) -> web.Response:
        """Accept the POST request for push registrations event callback."""
        auth_check = self.check_authorization_header(request)
        if not isinstance(auth_check, dict):
            return auth_check

        try:
            data: dict[str, str] = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON", HTTPStatus.BAD_REQUEST)

        event_payload: dict[str, Any] = {
            ATTR_TAG: data.get(ATTR_TAG),
            ATTR_TYPE: data[ATTR_TYPE],
            ATTR_TARGET: auth_check[ATTR_TARGET],
        }

        if data.get(ATTR_ACTION) is not None:
            event_payload[ATTR_ACTION] = data.get(ATTR_ACTION)

        if data.get(ATTR_DATA) is not None:
            event_payload[ATTR_DATA] = data.get(ATTR_DATA)

        try:
            event_payload = CALLBACK_EVENT_PAYLOAD_SCHEMA(event_payload)
        except vol.Invalid as ex:
            _LOGGER.warning(
                "Callback event payload is not valid: %s",
                humanize_error(event_payload, ex),
            )

        event_name = f"{NOTIFY_CALLBACK_EVENT}.{event_payload[ATTR_TYPE]}"
        hass = request.app[KEY_HASS]
        hass.bus.fire(event_name, event_payload)
        async_dispatcher_send(
            hass,
            DOMAIN,
            event_payload[ATTR_TARGET],
            event_payload[ATTR_TYPE],
            event_payload,
        )

        deprecated_event_bus(hass, event_name)

        return self.json({"status": "ok", "event": event_payload[ATTR_TYPE]})

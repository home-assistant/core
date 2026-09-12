"""HTML5 Push Messaging notification service."""

from contextlib import suppress
from datetime import datetime, timedelta
from http import HTTPStatus
import json
import logging
import time
from typing import TYPE_CHECKING, Any, cast, override
from urllib.parse import urlparse
import uuid
import warnings

from aiohttp import ClientError, ClientResponse, ClientSession
import jwt
from jwt.warnings import InsecureKeyLengthWarning
from py_vapid import Vapid
from pywebpush import WebPusher, WebPushException, webpush_async
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import URL_ROOT
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.json import load_json_object

from .const import (
    ATTR_ACTIONS,
    ATTR_REQUIRE_INTERACTION,
    ATTR_TAG,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PRV_KEY,
    ATTR_VAPID_PUB_KEY,
    DOMAIN,
    REGISTRATIONS_FILE,
    SERVICE_DISMISS,
)
from .entity import HTML5Entity, Registration
from .http import REGISTER_SCHEMA, async_register_http_views
from .issue import deprecated_dismiss_action_call, deprecated_notify_action_call

_LOGGER = logging.getLogger(__name__)


ATTR_URL = "url"
ATTR_DISMISS = "dismiss"
ATTR_PRIORITY = "priority"
DEFAULT_PRIORITY = "normal"
DEFAULT_TTL = 86400

DEFAULT_BADGE = "/static/images/notification-badge.png"
DEFAULT_ICON = "/static/icons/favicon-192x192.png"

ATTR_JWT = "jwt"

WS_TYPE_APPKEY = "notify/html5/appkey"
SCHEMA_WS_APPKEY = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_APPKEY}
)

# The number of days after the moment a notification is sent that a JWT
# is valid.
JWT_VALID_DAYS = 7
VAPID_CLAIM_VALID_HOURS = 12


DISMISS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DATA): dict,
    }
)


# Badge and timestamp are Chrome specific (not in official spec)
HTML5_SHOWNOTIFICATION_PARAMETERS = (
    "actions",
    "badge",
    "body",
    "dir",
    "icon",
    "image",
    "lang",
    "renotify",
    "requireInteraction",
    "tag",
    "timestamp",
    "vibrate",
    "silent",
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> HTML5NotificationService | None:
    """Get the HTML5 push notification service."""
    if config:
        return None
    if discovery_info is None:
        return None

    json_path = hass.config.path(REGISTRATIONS_FILE)

    registrations = await hass.async_add_executor_job(_load_config, json_path)

    vapid_pub_key: str = discovery_info[ATTR_VAPID_PUB_KEY]
    vapid_prv_key: str = discovery_info[ATTR_VAPID_PRV_KEY]
    vapid_email: str = discovery_info[ATTR_VAPID_EMAIL]

    @callback
    def websocket_appkey(
        _hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        connection.send_message(websocket_api.result_message(msg["id"], vapid_pub_key))

    websocket_api.async_register_command(
        hass, WS_TYPE_APPKEY, websocket_appkey, SCHEMA_WS_APPKEY
    )

    async_register_http_views(hass, json_path, registrations)

    session = async_get_clientsession(hass)
    return HTML5NotificationService(
        hass, session, vapid_prv_key, vapid_email, registrations, json_path
    )


def _load_config(filename: str) -> dict[str, Registration]:
    """Load configuration."""
    with suppress(HomeAssistantError):
        return cast(dict[str, Registration], load_json_object(filename))
    return {}


class HTML5NotificationService(BaseNotificationService):
    """Implement the notification service for HTML5."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        vapid_prv: str,
        vapid_email: str,
        registrations: dict[str, Registration],
        json_path: str,
    ) -> None:
        """Initialize the service."""
        self.session = session
        self._vapid_prv = vapid_prv
        self._vapid_email = vapid_email
        self.registrations = registrations
        self.registrations_json_path = json_path

        async def async_dismiss_message(service: ServiceCall) -> None:
            """Handle dismissing notification message service calls."""
            kwargs: dict[str, Any] = {}

            if self.targets is not None:
                kwargs[ATTR_TARGET] = self.targets
            elif service.data.get(ATTR_TARGET) is not None:
                kwargs[ATTR_TARGET] = service.data.get(ATTR_TARGET)

            kwargs[ATTR_DATA] = service.data.get(ATTR_DATA)

            await self.async_dismiss(**kwargs)

        hass.services.async_register(
            DOMAIN,
            SERVICE_DISMISS,
            async_dismiss_message,
            schema=DISMISS_SERVICE_SCHEMA,
        )

    @property
    @override
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {registration: registration for registration in self.registrations}

    async def async_dismiss(self, **kwargs: Any) -> None:
        """Dismisses a notification.

        This method must be run in the event loop.
        """

        deprecated_dismiss_action_call(self.hass)

        data: dict[str, Any] | None = kwargs.get(ATTR_DATA)
        tag: str = data.get(ATTR_TAG, "") if data else ""
        payload = {ATTR_TAG: tag, ATTR_DISMISS: True, ATTR_DATA: {}}

        await self._push_message(payload, **kwargs)

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        deprecated_notify_action_call(self.hass, kwargs.get(ATTR_TARGET))

        tag = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "badge": DEFAULT_BADGE,
            "body": message,
            ATTR_DATA: {},
            "icon": DEFAULT_ICON,
            ATTR_TAG: tag,
            ATTR_TITLE: kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
        }
        data: dict[str, Any] | None = kwargs.get(ATTR_DATA)
        if data:
            # Pick out fields that should go into the notification directly vs
            # into the notification data dictionary.

            data_tmp: dict[str, Any] = {}

            for key, val in data.items():
                if key in HTML5_SHOWNOTIFICATION_PARAMETERS:
                    payload[key] = val
                else:
                    data_tmp[key] = val

            payload[ATTR_DATA] = data_tmp

        if (
            payload[ATTR_DATA].get(ATTR_URL) is None
            and payload.get(ATTR_ACTIONS) is None
        ):
            payload[ATTR_DATA][ATTR_URL] = URL_ROOT

        await self._push_message(payload, **kwargs)

    async def _push_message(self, payload: dict[str, Any], **kwargs: Any) -> None:
        """Send the message."""

        timestamp = int(time.time())
        ttl = int(kwargs.get(ATTR_TTL, DEFAULT_TTL))
        priority: str = kwargs.get(ATTR_PRIORITY, DEFAULT_PRIORITY)
        if priority not in ["normal", "high"]:
            priority = DEFAULT_PRIORITY
        payload["timestamp"] = timestamp * 1000  # Javascript ms since epoch

        if not (targets := kwargs.get(ATTR_TARGET)):
            targets = self.registrations.keys()

        for target in list(targets):
            info = self.registrations.get(target)
            try:
                info = cast(Registration, REGISTER_SCHEMA(info))
            except vol.Invalid:
                _LOGGER.error(
                    "%s is not a valid HTML5 push notification target", target
                )
                continue
            subscription = info["subscription"]
            payload[ATTR_DATA][ATTR_JWT] = add_jwt(
                timestamp,
                target,
                payload[ATTR_TAG],
                subscription["keys"]["auth"],
            )

            webpusher = WebPusher(
                cast(dict[str, Any], info["subscription"]), aiohttp_session=self.session
            )

            endpoint = urlparse(subscription["endpoint"])
            vapid_claims = {
                "sub": f"mailto:{self._vapid_email}",
                "aud": f"{endpoint.scheme}://{endpoint.netloc}",
                "exp": timestamp + (VAPID_CLAIM_VALID_HOURS * 60 * 60),
            }
            vapid_headers = Vapid.from_string(self._vapid_prv).sign(vapid_claims)
            vapid_headers.update({"urgency": priority, "priority": priority})

            response = await webpusher.send_async(
                data=json.dumps(payload), headers=vapid_headers, ttl=ttl
            )

            if TYPE_CHECKING:
                assert not isinstance(response, str)

            if response.status == HTTPStatus.GONE:
                _LOGGER.info("Notification channel has expired")
                reg = self.registrations.pop(target)
                try:
                    await self.hass.async_add_executor_job(
                        save_json, self.registrations_json_path, self.registrations
                    )
                except HomeAssistantError:
                    self.registrations[target] = reg
                    _LOGGER.error("Error saving registration")
                else:
                    _LOGGER.info("Configuration saved")
            elif response.status >= HTTPStatus.BAD_REQUEST:
                _LOGGER.error(
                    "There was an issue sending the notification %s: %s",
                    response.status,
                    await response.text(),
                )


def add_jwt(timestamp: int, target: str, tag: str, jwt_secret: str) -> str:
    """Create JWT json to put into payload."""

    jwt_exp = datetime.fromtimestamp(timestamp) + timedelta(days=JWT_VALID_DAYS)
    jwt_claims = {
        "exp": jwt_exp,
        "nbf": timestamp,
        "iat": timestamp,
        ATTR_TARGET: target,
        ATTR_TAG: tag,
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureKeyLengthWarning)
        return jwt.encode(jwt_claims, jwt_secret)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notification entity platform."""

    json_path = hass.config.path(REGISTRATIONS_FILE)
    registrations = await hass.async_add_executor_job(_load_config, json_path)

    session = async_get_clientsession(hass)
    async_add_entities(
        HTML5NotifyEntity(config_entry, target, registrations, session, json_path)
        for target in registrations
    )


class HTML5NotifyEntity(HTML5Entity, NotifyEntity):
    """Representation of a notification entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _key = "device"

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to a device via notify.send_message action."""
        await self._webpush(
            title=title or ATTR_TITLE_DEFAULT,
            message=message,
            badge=DEFAULT_BADGE,
            icon=DEFAULT_ICON,
        )

    async def send_push_notification(self, **kwargs: Any) -> None:
        """Send a message to a device via html5.send_message action."""
        await self._webpush(**kwargs)
        self._async_record_notification()

    async def dismiss_notification(self, tag: str = "") -> None:
        """Dismiss a message via html5.dismiss_message action."""
        await self._webpush(dismiss=True, tag=tag)
        self._async_record_notification()

    async def _webpush(
        self,
        message: str | None = None,
        timestamp: datetime | None = None,
        ttl: timedelta | None = None,
        urgency: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Shared internal helper to push messages."""
        payload: dict[str, Any] = kwargs

        if message is not None:
            payload["body"] = message

        payload.setdefault(ATTR_TAG, str(uuid.uuid4()))
        ts = int(timestamp.timestamp()) if timestamp else int(time.time())
        payload[ATTR_TIMESTAMP] = ts * 1000

        if ATTR_REQUIRE_INTERACTION in payload:
            payload["requireInteraction"] = payload.pop(ATTR_REQUIRE_INTERACTION)

        payload.setdefault(ATTR_DATA, {})
        payload[ATTR_DATA][ATTR_JWT] = add_jwt(
            ts,
            self.target,
            payload[ATTR_TAG],
            self.registration["subscription"]["keys"]["auth"],
        )

        endpoint = urlparse(self.registration["subscription"]["endpoint"])
        vapid_claims = {
            "sub": f"mailto:{self.config_entry.data[ATTR_VAPID_EMAIL]}",
            "aud": f"{endpoint.scheme}://{endpoint.netloc}",
            "exp": ts + (VAPID_CLAIM_VALID_HOURS * 60 * 60),
        }

        try:
            response = await webpush_async(
                cast(dict[str, Any], self.registration["subscription"]),
                json.dumps(payload),
                self.config_entry.data[ATTR_VAPID_PRV_KEY],
                vapid_claims,
                ttl=int(ttl.total_seconds()) if ttl is not None else DEFAULT_TTL,
                headers={"Urgency": urgency} if urgency else None,
                aiohttp_session=self.session,
            )
            cast(ClientResponse, response).raise_for_status()
        except WebPushException as e:
            if cast(ClientResponse, e.response).status == HTTPStatus.GONE:
                reg = self.registrations.pop(self.target)
                try:
                    await self.hass.async_add_executor_job(
                        save_json, self.json_path, self.registrations
                    )
                except HomeAssistantError:
                    self.registrations[self.target] = reg
                    _LOGGER.error("Error saving registration")

                self.async_write_ha_state()
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="channel_expired",
                    translation_placeholders={"target": self.target},
                ) from e

            _LOGGER.debug("Full exception", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_error",
                translation_placeholders={"target": self.target},
            ) from e
        except ClientError as e:
            _LOGGER.debug("Full exception", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"target": self.target},
            ) from e

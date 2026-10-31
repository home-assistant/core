"""HTML5 Push Messaging notification service."""

from contextlib import suppress
from datetime import datetime, timedelta
from http import HTTPStatus
import json
import logging
import time
from typing import Any, cast, override
from urllib.parse import urlparse
import uuid
import warnings

from aiohttp import ClientError, ClientResponse
import jwt
from jwt.warnings import InsecureKeyLengthWarning
from pywebpush import WebPushException, webpush_async

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE_DEFAULT,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import save_json
from homeassistant.util.json import load_json_object

from .const import (
    ATTR_REQUIRE_INTERACTION,
    ATTR_TAG,
    ATTR_TIMESTAMP,
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PRV_KEY,
    DOMAIN,
    REGISTRATIONS_FILE,
)
from .entity import HTML5Entity, Registration

_LOGGER = logging.getLogger(__name__)


ATTR_DISMISS = "dismiss"
DEFAULT_PRIORITY = "normal"
DEFAULT_TTL = 86400

DEFAULT_BADGE = "/static/images/notification-badge.png"
DEFAULT_ICON = "/static/icons/favicon-192x192.png"

ATTR_JWT = "jwt"

# The number of days after the moment a notification is sent that a JWT
# is valid.
JWT_VALID_DAYS = 7
VAPID_CLAIM_VALID_HOURS = 12


def _load_config(filename: str) -> dict[str, Registration]:
    """Load configuration."""
    with suppress(HomeAssistantError):
        return cast(dict[str, Registration], load_json_object(filename))
    return {}


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

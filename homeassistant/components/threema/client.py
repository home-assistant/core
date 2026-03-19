"""Threema Gateway API client."""

from __future__ import annotations

import logging

from threema.gateway import Connection, GatewayError, key
from threema.gateway.e2e import TextMessage
from threema.gateway.exception import GatewayServerError
from threema.gateway.simple import TextMessage as SimpleTextMessage

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# HTTP 401 from Threema Gateway means invalid credentials
_HTTP_UNAUTHORIZED = 401


class ThreemaConnectionError(Exception):
    """Error to indicate a connection issue with the Threema Gateway."""


class ThreemaAuthError(Exception):
    """Error to indicate invalid credentials for the Threema Gateway."""


class ThreemaSendError(Exception):
    """Error to indicate a message send failure."""


class ThreemaAPIClient:
    """Threema Gateway API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        gateway_id: str,
        api_secret: str,
        private_key: str | None = None,
    ) -> None:
        """Initialize the Threema API client."""
        self.hass = hass
        self.gateway_id = gateway_id
        self.api_secret = api_secret
        self.private_key = private_key

    def _get_connection(self) -> Connection:
        """Get a Threema Gateway connection.

        Note: Connection manages its own aiohttp session lifecycle.
        Do not pass HA's shared session as Connection will close it.
        """
        return Connection(
            identity=self.gateway_id,
            secret=self.api_secret,
            key=self.private_key,
        )

    async def validate_credentials(self) -> None:
        """Validate the Gateway credentials by checking credits.

        Raises ThreemaAuthError for invalid credentials.
        Raises ThreemaConnectionError for other failures.
        """
        try:
            async with self._get_connection() as conn:
                remaining_credits = await conn.get_credits()
                _LOGGER.debug(
                    "Gateway credentials validated, credits: %s",
                    remaining_credits,
                )
        except GatewayServerError as err:
            if err.status == _HTTP_UNAUTHORIZED:
                raise ThreemaAuthError("Invalid Threema Gateway credentials") from err
            raise ThreemaConnectionError(
                f"Gateway server error validating credentials: {err}"
            ) from err
        except GatewayError as err:
            raise ThreemaConnectionError(
                f"Gateway error validating credentials: {err}"
            ) from err
        except Exception as err:
            raise ThreemaConnectionError(
                f"Failed to validate credentials: {err}"
            ) from err

    async def send_text_message(self, recipient_id: str, text: str) -> str:
        """Send a text message to a Threema ID.

        Returns the message ID on success.
        Raises ThreemaSendError on failure.
        """
        try:
            async with self._get_connection() as conn:
                if self.private_key:
                    _LOGGER.debug("Sending E2E encrypted message to %s", recipient_id)
                    message = TextMessage(
                        connection=conn,
                        to_id=recipient_id,
                        text=text,
                    )
                else:
                    _LOGGER.debug("Sending simple message to %s", recipient_id)
                    message = SimpleTextMessage(
                        connection=conn,
                        to_id=recipient_id,
                        text=text,
                    )

                message_id: str = await message.send()
                _LOGGER.debug("Message sent to %s (ID: %s)", recipient_id, message_id)
                return message_id
        except GatewayServerError as err:
            if err.status == _HTTP_UNAUTHORIZED:
                raise ThreemaAuthError("Invalid Threema Gateway credentials") from err
            raise ThreemaSendError(
                f"Gateway server error sending message to {recipient_id}: {err}"
            ) from err
        except GatewayError as err:
            raise ThreemaSendError(
                f"Gateway error sending message to {recipient_id}: {err}"
            ) from err
        except Exception as err:
            raise ThreemaSendError(
                f"Failed to send message to {recipient_id}: {err}"
            ) from err


def generate_key_pair() -> tuple[str, str]:
    """Generate a new key pair for E2E encryption using official SDK.

    Returns tuple of (private_key, public_key) as encoded strings.
    """
    private_key_obj, public_key_obj = key.Key.generate_pair()
    private_key_str = key.Key.encode(private_key_obj)
    public_key_str = key.Key.encode(public_key_obj)
    return private_key_str, public_key_str

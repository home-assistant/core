import base64  # noqa: D100
import json
import logging
import time

import aiohttp  # noqa: D100

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class TrestIdentityService:
    """A class representing the Trest Identity Api."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Set up TrestIdentityService."""

        self.base_url = "https://identity.trest.se:443"
        self.token = ""
        self.hass = hass
        self.username = username
        self.password = password

    async def authenticate_async(self) -> None:
        """Authenticate the class instance asynchronously."""
        payload = {"email": self.username, "password": self.password}
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session, session.post(
            self.base_url + "/api/v1/user/authenticate",
            data=json.dumps(payload),
            headers=headers,
            timeout=3,
        ) as response:
            response_text = await response.text()
            self.token = response_text

    async def renew_token_async(self) -> None:
        """Renew the class instance token if it is not valid."""

        if (self.token is None or self.token == "") or self.check_token_is_expired():
            await self.authenticate_async()

    def check_token_is_expired(self) -> bool:
        """Check if the token set in the instance of the class is expired."""

        try:
            token_payload = self.token.split(".")
            token_payload_encoded = token_payload[1]

            # Add padding if necessary
            missing_padding = len(token_payload_encoded) % 4
            if missing_padding != 0:
                token_payload_encoded += "=" * (4 - missing_padding)

            token_payload_bytes = base64.urlsafe_b64decode(token_payload_encoded)
            token_payload_json = json.loads(token_payload_bytes.decode("utf-8"))

            current_time = time.time()
            token_expire_unix = token_payload_json["exp"]

            return current_time < token_expire_unix
        except IndexError:
            return False

import base64  # noqa: D100
import json
import time

import requests


class TrestIdentityService:
    """A class representing the Trest Identity Api."""

    def __init__(self) -> None:
        """Set up TrestIdentityService."""

        self.base_url = "https://identity.trest.se:443"
        self.token = ""

    def authenticate(self, username: str, password: str) -> None:
        """Authenticate the class instance."""

        payload = {"email": username, "password": password}
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            self.base_url + "/api/v1/user/authenticate",
            data=json.dumps(payload),
            headers=headers,
            timeout=3,
        )

        self.token = response.text

    def renew_token(self, username: str, password: str) -> None:
        """Renew the class instance token if it is not valid."""

        if (self.token is None or self.token == "") or self.check_token_is_expired():
            self.authenticate(username, password)

    def check_token_is_expired(self) -> bool:
        """Check if the token set in the instance of the class is expired."""

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

        return current_time > token_expire_unix

"""Helper functions for Overseerr."""
from typing import Any

from overseerr_api import ApiClient, AuthApi, Configuration, User

from homeassistant.const import CONF_API_KEY, CONF_URL


def setup_client(data: dict[str, Any]) -> User | None:
    """Validate the user input allows us to connect to Overseerr."""
    overseerr_config = Configuration(
        api_key={"apiKey": data.get(CONF_API_KEY, "")},
        host=data[CONF_URL],
    )

    overseerr_client = ApiClient(overseerr_config)
    auth_api = AuthApi(overseerr_client)

    return auth_api.auth_me_get()

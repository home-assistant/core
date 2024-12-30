"""Class for interacting with Appwrite instance."""

import logging
from typing import Any

from appwrite.client import AppwriteException, Client
from appwrite.services.functions import Functions
from appwrite.services.health import Health

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_PROJECT_ID

_LOGGER = logging.getLogger(__name__)


type AppwriteConfigEntry = ConfigEntry[AppwriteClient]


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidUrl(HomeAssistantError):
    """Error to indicate there is invalid url."""


class AppwriteClient:
    """Appwrite client for credential validation and services."""

    def __init__(
        self,
        data: dict[str, Any],
    ) -> None:
        """Initialize the API client."""
        self.endpoint = f"{data[CONF_HOST]}/v1"
        self.project_id = data[CONF_PROJECT_ID]
        self.api_key = data[CONF_API_KEY]
        self._appwrite_client = (
            Client()
            .set_endpoint(self.endpoint)
            .set_project(self.project_id)
            .set_key(self.api_key)
        )

    def async_validate_credentials(self) -> bool:
        """Check if we can authenticate with the host."""
        try:
            health_api = Health(self._appwrite_client)
            result = health_api.get()
            _LOGGER.debug("Health API response: %s", result)
        except AppwriteException as ae:
            _LOGGER.error(ae.message)
            return False
        return True

    def async_execute_function(
        self,
        function_id: Any | None,
        body: Any,
        path: Any,
        headers: Any,
        scheduled_at: Any,
        xasync: Any,
        method: Any,
    ) -> None:
        """Execute function."""
        functions = Functions(self._appwrite_client)
        _LOGGER.debug("Executed function '%s'", function_id)
        return functions.create_execution(
            function_id, body, xasync, path, method, headers, scheduled_at
        )

"""Services file."""

from hashlib import md5

import voluptuous as vol

from homeassistant.const import CONF_DESCRIPTION, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.loader import async_get_integration
from homeassistant.util.yaml import load_yaml_dict

from .appwrite import AppwriteConfigEntry
from .const import (
    CONF_FIELDS,
    DOMAIN,
    EXECUTE_FUNCTION,
    FUNCTION_ASYNC,
    FUNCTION_BODY,
    FUNCTION_HEADERS,
    FUNCTION_ID,
    FUNCTION_METHOD,
    FUNCTION_PATH,
    FUNCTION_SCHEDULED_AT,
)

RESPONSE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FUNCTION_ID): str,
        vol.Optional(FUNCTION_BODY): str,
        vol.Optional(FUNCTION_PATH): str,
        vol.Optional(FUNCTION_HEADERS): dict[str, str],
        vol.Optional(FUNCTION_SCHEDULED_AT): str,
        vol.Optional(FUNCTION_ASYNC): bool,
        # Reference https://github.com/appwrite/sdk-for-node/blob/main/src/enums/execution-method.ts
        vol.Optional(FUNCTION_METHOD): vol.In(
            ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        ),
    }
)


class AppwriteServices:
    """Class to handle Appwrite integration Services."""

    def __init__(self, hass: HomeAssistant, config_entry: AppwriteConfigEntry) -> None:
        """Initialise services."""
        self.hass = hass
        self.appwrite_client = config_entry.runtime_data

    async def setup(self):
        """Initialise the services in Hass."""
        service_name = self.__build_service_name()
        self.hass.services.async_register(
            DOMAIN,
            service_name,
            self.async_execute_function,
            schema=RESPONSE_SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

        # Load service descriptions from appwrite/services.yaml
        integration = await async_get_integration(self.hass, DOMAIN)
        services_yaml = integration.file_path / "services.yaml"
        services_dict = await self.hass.async_add_executor_job(
            load_yaml_dict, str(services_yaml)
        )

        # Register the service description
        service_desc = {
            CONF_NAME: "Execute Function",
            CONF_DESCRIPTION: ("Trigger a function in Appwrite"),
            CONF_FIELDS: services_dict[EXECUTE_FUNCTION][CONF_FIELDS],
        }
        async_set_service_schema(self.hass, DOMAIN, service_name, service_desc)

    async def async_execute_function(self, service_call: ServiceCall) -> None:
        """Execute execute function service call.

        This will take function id, function body and return Appwrite's execution response.

        """
        return await self.hass.async_add_executor_job(
            self.appwrite_client.async_execute_function,
            service_call.data.get(FUNCTION_ID),
            service_call.data.get(FUNCTION_BODY, None),
            service_call.data.get(FUNCTION_PATH, None),
            service_call.data.get(FUNCTION_HEADERS, None),
            service_call.data.get(FUNCTION_SCHEDULED_AT, None),
            service_call.data.get(FUNCTION_ASYNC, False),  # default is false
            service_call.data.get(FUNCTION_METHOD, "GET"),  # default is GET
        )

    def __build_service_name(self) -> str:
        service_id = md5(
            f"{self.appwrite_client.endpoint}_{self.appwrite_client.project_id}".encode()
        ).hexdigest()
        return f"{EXECUTE_FUNCTION}_{service_id}"

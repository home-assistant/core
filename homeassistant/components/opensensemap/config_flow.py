"""Config flow for OpenSenseMap."""
from typing import Any, cast

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_ID, DOMAIN


async def request_station_data(
    hass: HomeAssistant, station_id: str
) -> tuple[dict[str, Any], str]:
    """Connect to API and try to receive data for given station_id."""
    errors = {}
    received_name = ""
    station_api = OpenSenseMap(station_id, async_get_clientsession(hass))

    try:
        await station_api.get_data()

    except OpenSenseMapError:
        errors["base"] = "cannot_connect"

    else:
        if (received_name := station_api.data.get("name")) is None:
            errors[CONF_STATION_ID] = "invalid_id"

    return errors, received_name


class OpenSenseMapConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            name_in_conf = user_input.get(CONF_NAME)

            errors, received_name = await request_station_data(self.hass, station_id)
            await self.async_set_unique_id(station_id)
            self._abort_if_unique_id_configured()

            name = name_in_conf or received_name
            config_data = {
                CONF_STATION_ID: station_id,
                CONF_NAME: name,
            }
            if not errors:
                return self.async_create_entry(title=name, data=config_data)

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                }
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""

        def create_repair(error: str | None = None) -> None:
            if error:
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_yaml_import_issue_{error}",
                    breaks_in_ha_version="2024.8.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key=f"deprecated_yaml_import_issue_{error}",
                    translation_placeholders={
                        "url": "/config/integrations/dashboard/add?domain=opensensemap"
                    },
                )
            else:
                async_create_issue(
                    self.hass,
                    HOMEASSISTANT_DOMAIN,
                    f"deprecated_yaml_{DOMAIN}",
                    breaks_in_ha_version="2024.8.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": "Opensensemap",
                    },
                )

        station_id = cast(str, import_config.get(CONF_STATION_ID))
        name_in_config = import_config.get(CONF_NAME)

        errors, received_name = await request_station_data(self.hass, station_id)
        if error := errors.get("base"):
            create_repair(error)
            return self.async_abort(reason=error)

        if error := errors.get(CONF_STATION_ID):
            create_repair(error)
            return self.async_abort(reason=error)

        create_repair()

        await self.async_set_unique_id(station_id)
        self._abort_if_unique_id_configured()

        name = name_in_config or received_name
        if not name_in_config:
            import_config[CONF_NAME] = name

        return self.async_create_entry(title=name, data=import_config)

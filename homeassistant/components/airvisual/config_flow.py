"""Define a config flow manager for AirVisual."""
import asyncio

from pyairvisual import CloudAPI, NodeSamba
from pyairvisual.errors import (
    AirVisualError,
    InvalidKeyError,
    NodeProError,
    NotFoundError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from . import async_get_geography_id
from .const import (  # pylint: disable=unused-import
    CONF_CITY,
    CONF_COUNTRY,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    INTEGRATION_TYPE_NODE_PRO,
    LOGGER,
)

API_KEY_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})
GEOGRAPHY_NAME_SCHEMA = API_KEY_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STATE): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
    }
)
NODE_PRO_SCHEMA = vol.Schema(
    {vol.Required(CONF_IP_ADDRESS): str, vol.Required(CONF_PASSWORD): cv.string}
)
PICK_INTEGRATION_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): vol.In(
            [
                INTEGRATION_TYPE_GEOGRAPHY_COORDS,
                INTEGRATION_TYPE_GEOGRAPHY_NAME,
                INTEGRATION_TYPE_NODE_PRO,
            ]
        )
    }
)


class AirVisualFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an AirVisual config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._entry_data_for_reauth = None
        self._geo_id = None

    @property
    def geography_coords_schema(self):
        """Return the data schema for the cloud API."""
        return API_KEY_DATA_SCHEMA.extend(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

    async def _async_finish_geography(self, user_input, integration_type):
        """Validate a Cloud API key."""
        websession = aiohttp_client.async_get_clientsession(self.hass)
        cloud_api = CloudAPI(user_input[CONF_API_KEY], session=websession)

        # If this is the first (and only the first) time we've seen this API key, check
        # that it's valid:
        valid_keys = self.hass.data.setdefault("airvisual_checked_api_keys", set())
        valid_keys_lock = self.hass.data.setdefault(
            "airvisual_checked_api_keys_lock", asyncio.Lock()
        )

        if integration_type == INTEGRATION_TYPE_GEOGRAPHY_COORDS:
            coro = cloud_api.air_quality.nearest_city()
            error_schema = self.geography_coords_schema
            error_step = "geography_by_coords"
        else:
            coro = cloud_api.air_quality.city(
                user_input[CONF_CITY], user_input[CONF_STATE], user_input[CONF_COUNTRY]
            )
            error_schema = GEOGRAPHY_NAME_SCHEMA
            error_step = "geography_by_name"

        async with valid_keys_lock:
            if user_input[CONF_API_KEY] not in valid_keys:
                try:
                    await coro
                except InvalidKeyError:
                    return self.async_show_form(
                        step_id=error_step,
                        data_schema=error_schema,
                        errors={CONF_API_KEY: "invalid_api_key"},
                    )
                except NotFoundError:
                    return self.async_show_form(
                        step_id=error_step,
                        data_schema=error_schema,
                        errors={CONF_CITY: "location_not_found"},
                    )
                except AirVisualError as err:
                    LOGGER.error(err)
                    return self.async_show_form(
                        step_id=error_step,
                        data_schema=error_schema,
                        errors={"base": "unknown"},
                    )

                valid_keys.add(user_input[CONF_API_KEY])

        existing_entry = await self.async_set_unique_id(self._geo_id)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=f"Cloud API ({self._geo_id})",
            data={**user_input, CONF_INTEGRATION_TYPE: integration_type},
        )

    async def _async_init_geography(self, user_input, integration_type):
        """Handle the initialization of the integration via the cloud API."""
        self._geo_id = async_get_geography_id(user_input)
        await self._async_set_unique_id(self._geo_id)
        self._abort_if_unique_id_configured()
        return await self._async_finish_geography(user_input, integration_type)

    async def _async_set_unique_id(self, unique_id):
        """Set the unique ID of the config flow and abort if it already exists."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return AirVisualOptionsFlowHandler(config_entry)

    async def async_step_geography_by_coords(self, user_input=None):
        """Handle the initialization of the cloud API based on latitude/longitude."""
        if not user_input:
            return self.async_show_form(
                step_id="geography_by_coords", data_schema=self.geography_coords_schema
            )

        return await self._async_init_geography(
            user_input, INTEGRATION_TYPE_GEOGRAPHY_COORDS
        )

    async def async_step_geography_by_name(self, user_input=None):
        """Handle the initialization of the cloud API based on city/state/country."""
        if not user_input:
            return self.async_show_form(
                step_id="geography_by_name", data_schema=GEOGRAPHY_NAME_SCHEMA
            )

        return await self._async_init_geography(
            user_input, INTEGRATION_TYPE_GEOGRAPHY_NAME
        )

    async def async_step_node_pro(self, user_input=None):
        """Handle the initialization of the integration with a Node/Pro."""
        if not user_input:
            return self.async_show_form(step_id="node_pro", data_schema=NODE_PRO_SCHEMA)

        await self._async_set_unique_id(user_input[CONF_IP_ADDRESS])

        node = NodeSamba(user_input[CONF_IP_ADDRESS], user_input[CONF_PASSWORD])

        try:
            await node.async_connect()
        except NodeProError as err:
            LOGGER.error("Error connecting to Node/Pro unit: %s", err)
            return self.async_show_form(
                step_id="node_pro",
                data_schema=NODE_PRO_SCHEMA,
                errors={CONF_IP_ADDRESS: "cannot_connect"},
            )

        await node.async_disconnect()

        return self.async_create_entry(
            title=f"Node/Pro ({user_input[CONF_IP_ADDRESS]})",
            data={**user_input, CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO},
        )

    async def async_step_reauth(self, data):
        """Handle configuration by re-auth."""
        self._entry_data_for_reauth = data
        self._geo_id = async_get_geography_id(data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=API_KEY_DATA_SCHEMA
            )

        conf = {CONF_API_KEY: user_input[CONF_API_KEY], **self._entry_data_for_reauth}

        return await self._async_finish_geography(
            conf, self._entry_data_for_reauth[CONF_INTEGRATION_TYPE]
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=PICK_INTEGRATION_TYPE_SCHEMA
            )

        if user_input["type"] == INTEGRATION_TYPE_GEOGRAPHY_COORDS:
            return await self.async_step_geography_by_coords()
        if user_input["type"] == INTEGRATION_TYPE_GEOGRAPHY_NAME:
            return await self.async_step_geography_by_name()
        return await self.async_step_node_pro()


class AirVisualOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an AirVisual options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_ON_MAP,
                        default=self.config_entry.options.get(CONF_SHOW_ON_MAP),
                    ): bool
                }
            ),
        )

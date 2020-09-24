"""Define a config flow manager for AirVisual."""
import asyncio

from pyairvisual import CloudAPI, NodeSamba
from pyairvisual.errors import InvalidKeyError, NodeProError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from . import async_get_geography_id
from .const import (  # pylint: disable=unused-import
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
    INTEGRATION_TYPE_NODE_PRO,
    LOGGER,
)


class AirVisualFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an AirVisual config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._geo_id = None
        self._latitude = None
        self._longitude = None

        self.api_key_data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})

    @property
    def geography_schema(self):
        """Return the data schema for the cloud API."""
        return self.api_key_data_schema.extend(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

    @property
    def pick_integration_type_schema(self):
        """Return the data schema for picking the integration type."""
        return vol.Schema(
            {
                vol.Required("type"): vol.In(
                    [INTEGRATION_TYPE_GEOGRAPHY, INTEGRATION_TYPE_NODE_PRO]
                )
            }
        )

    @property
    def node_pro_schema(self):
        """Return the data schema for a Node/Pro."""
        return vol.Schema(
            {vol.Required(CONF_IP_ADDRESS): str, vol.Required(CONF_PASSWORD): str}
        )

    async def _async_set_unique_id(self, unique_id):
        """Set the unique ID of the config flow and abort if it already exists."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return AirVisualOptionsFlowHandler(config_entry)

    async def async_step_geography(self, user_input=None):
        """Handle the initialization of the integration via the cloud API."""
        if not user_input:
            return self.async_show_form(
                step_id="geography", data_schema=self.geography_schema
            )

        self._geo_id = async_get_geography_id(user_input)
        await self._async_set_unique_id(self._geo_id)
        self._abort_if_unique_id_configured()

        # Find older config entries without unique ID:
        for entry in self._async_current_entries():
            if entry.version != 1:
                continue

            if any(
                self._geo_id == async_get_geography_id(geography)
                for geography in entry.data[CONF_GEOGRAPHIES]
            ):
                return self.async_abort(reason="already_configured")

        websession = aiohttp_client.async_get_clientsession(self.hass)
        cloud_api = CloudAPI(user_input[CONF_API_KEY], session=websession)

        # If this is the first (and only the first) time we've seen this API key, check
        # that it's valid:
        checked_keys = self.hass.data.setdefault("airvisual_checked_api_keys", set())
        check_keys_lock = self.hass.data.setdefault(
            "airvisual_checked_api_keys_lock", asyncio.Lock()
        )

        async with check_keys_lock:
            if user_input[CONF_API_KEY] not in checked_keys:
                try:
                    await cloud_api.air_quality.nearest_city()
                except InvalidKeyError:
                    return self.async_show_form(
                        step_id="geography",
                        data_schema=self.geography_schema,
                        errors={CONF_API_KEY: "invalid_api_key"},
                    )

                checked_keys.add(user_input[CONF_API_KEY])

            return await self.async_step_geography_finish(user_input)

    async def async_step_geography_finish(self, user_input=None):
        """Handle the finalization of a Cloud API config entry."""
        existing_entry = await self.async_set_unique_id(self._geo_id)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=f"Cloud API ({self._geo_id})",
            data={**user_input, CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_geography(import_config)

    async def async_step_node_pro(self, user_input=None):
        """Handle the initialization of the integration with a Node/Pro."""
        if not user_input:
            return self.async_show_form(
                step_id="node_pro", data_schema=self.node_pro_schema
            )

        await self._async_set_unique_id(user_input[CONF_IP_ADDRESS])

        node = NodeSamba(user_input[CONF_IP_ADDRESS], user_input[CONF_PASSWORD])

        try:
            await node.async_connect()
        except NodeProError as err:
            LOGGER.error("Error connecting to Node/Pro unit: %s", err)
            return self.async_show_form(
                step_id="node_pro",
                data_schema=self.node_pro_schema,
                errors={CONF_IP_ADDRESS: "unable_to_connect"},
            )

        await node.async_disconnect()

        return self.async_create_entry(
            title=f"Node/Pro ({user_input[CONF_IP_ADDRESS]})",
            data={**user_input, CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO},
        )

    async def async_step_reauth(self, data):
        """Handle configuration by re-auth."""
        self._latitude = data[CONF_LATITUDE]
        self._longitude = data[CONF_LONGITUDE]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=self.api_key_data_schema
            )

        conf = {
            CONF_API_KEY: user_input[CONF_API_KEY],
            CONF_LATITUDE: self._latitude,
            CONF_LONGITUDE: self._longitude,
        }

        self._geo_id = async_get_geography_id(conf)

        return await self.async_step_geography_finish(conf)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=self.pick_integration_type_schema
            )

        if user_input["type"] == INTEGRATION_TYPE_GEOGRAPHY:
            return await self.async_step_geography()
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

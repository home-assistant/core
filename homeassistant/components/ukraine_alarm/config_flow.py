"""Config flow for Ukraine Alarm."""
import aiohttp
from ukrainealarm.client import Client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_REGION
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class UkraineAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ukraine Alarm."""

    VERSION = 1

    def __init__(self):
        """Initialize a new UkraineAlarmConfigFlow."""
        self.api_key = None
        self.states = None
        self.selected_region = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            websession = async_get_clientsession(self.hass)
            try:
                regions = await Client(
                    websession, user_input[CONF_API_KEY]
                ).get_regions()
            except aiohttp.ClientResponseError as ex:
                errors["base"] = "invalid_api_key" if ex.status == 401 else "unknown"
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "unknown"

            if not regions:
                errors["base"] = "unknown"

            if not errors:
                self.api_key = user_input[CONF_API_KEY]
                self.states = regions["states"]
                return await self.async_step_state()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors, last_step=False
        )

    async def async_step_state(self, user_input=None):
        """Handle user-chosen state."""
        if user_input is not None:
            self.selected_region = _find(self.states, user_input[CONF_REGION])
            if self.selected_region["regionChildIds"]:
                return await self.async_step_district()
            return await self._async_finish_flow()

        regions_object = _make_regions_object(self.states)

        schema = vol.Schema(
            {
                vol.Required(CONF_REGION): vol.In(regions_object),
            }
        )

        return self.async_show_form(
            step_id="state", data_schema=schema, last_step=False
        )

    async def async_step_district(self, user_input=None):
        """Handle user-chosen district."""
        if user_input is not None:
            if CONF_REGION not in user_input:
                return await self._async_finish_flow()
            self.selected_region = _find(
                self.selected_region["regionChildIds"], user_input[CONF_REGION]
            )
            if self.selected_region["regionChildIds"]:
                return await self.async_step_community()
            return await self._async_finish_flow()

        regions_object = _make_regions_object(self.selected_region["regionChildIds"])

        schema = vol.Schema(
            {
                vol.Optional(CONF_REGION): vol.In(regions_object),
            }
        )

        return self.async_show_form(
            step_id="district", data_schema=schema, last_step=False
        )

    async def async_step_community(self, user_input=None):
        """Handle user-chosen community."""
        if user_input is not None:
            if CONF_REGION in user_input:
                self.selected_region = _find(
                    self.selected_region["regionChildIds"], user_input[CONF_REGION]
                )
            return await self._async_finish_flow()

        regions_object = _make_regions_object(self.selected_region["regionChildIds"])

        schema = vol.Schema(
            {
                vol.Optional(CONF_REGION): vol.In(regions_object),
            }
        )

        return self.async_show_form(
            step_id="community", data_schema=schema, last_step=True
        )

    async def _async_finish_flow(self):
        """Finish the setup."""
        await self.async_set_unique_id(self.selected_region["regionId"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.selected_region["regionName"],
            data={
                CONF_API_KEY: self.api_key,
                CONF_REGION: self.selected_region["regionId"],
                CONF_NAME: self.selected_region["regionName"],
            },
        )


def _find(regions, region_id):
    return next((region for region in regions if region["regionId"] == region_id), None)


def _make_regions_object(regions):
    regions_list = []
    for region in regions:
        regions_list.append(
            {
                "id": region["regionId"],
                "name": region["regionName"],
            }
        )
    regions_list = sorted(regions_list, key=lambda region: region["name"].lower())
    regions_object = {}
    for region in regions_list:
        regions_object[region["id"]] = region["name"]

    return regions_object

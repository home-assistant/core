"""Config flow for Ukraine Alarm."""
from __future__ import annotations

import asyncio

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
            except asyncio.TimeoutError:
                errors["base"] = "timeout"

            if not errors and not regions:
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
            step_id="user",
            data_schema=schema,
            description_placeholders={"api_url": "https://api.ukrainealarm.com/"},
            errors=errors,
            last_step=False,
        )

    async def async_step_state(self, user_input=None):
        """Handle user-chosen state."""
        return await self._handle_pick_region("state", "district", user_input)

    async def async_step_district(self, user_input=None):
        """Handle user-chosen district."""
        return await self._handle_pick_region("district", "community", user_input)

    async def async_step_community(self, user_input=None):
        """Handle user-chosen community."""
        return await self._handle_pick_region("community", None, user_input, True)

    async def _handle_pick_region(
        self, step_id: str, next_step: str | None, user_input, last_step=False
    ):
        """Handle picking a (sub)region."""
        if self.selected_region:
            source = self.selected_region["regionChildIds"]
        else:
            source = self.states

        if user_input is not None:
            # Only offer to browse subchildren if picked region wasn't the previously picked one
            if (
                not self.selected_region
                or user_input[CONF_REGION] != self.selected_region["regionId"]
            ):
                self.selected_region = _find(source, user_input[CONF_REGION])

                if next_step and self.selected_region["regionChildIds"]:
                    return await getattr(self, f"async_step_{next_step}")()

            return await self._async_finish_flow()

        regions = {}
        if self.selected_region:
            regions[self.selected_region["regionId"]] = self.selected_region[
                "regionName"
            ]

        regions.update(_make_regions_object(source))

        schema = vol.Schema(
            {
                vol.Required(CONF_REGION): vol.In(regions),
            }
        )

        return self.async_show_form(
            step_id=step_id, data_schema=schema, last_step=last_step
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

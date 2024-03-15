"""Config flow for Ukraine Alarm."""

from __future__ import annotations

import logging

import aiohttp
from uasiren.client import Client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME, CONF_REGION
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UkraineAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Ukraine Alarm."""

    VERSION = 1

    def __init__(self):
        """Initialize a new UkraineAlarmConfigFlow."""
        self.states = None
        self.selected_region = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if len(self._async_current_entries()) == 5:
            return self.async_abort(reason="max_regions")

        if not self.states:
            websession = async_get_clientsession(self.hass)
            reason = None
            unknown_err_msg = None
            try:
                regions = await Client(websession).get_regions()
            except aiohttp.ClientResponseError as ex:
                if ex.status == 429:
                    reason = "rate_limit"
                else:
                    reason = "unknown"
                    unknown_err_msg = str(ex)
            except aiohttp.ClientConnectionError:
                reason = "cannot_connect"
            except aiohttp.ClientError as ex:
                reason = "unknown"
                unknown_err_msg = str(ex)
            except TimeoutError:
                reason = "timeout"

            if not reason and not regions:
                reason = "unknown"
                unknown_err_msg = "no regions returned"

            if unknown_err_msg:
                _LOGGER.error("Failed to connect to the service: %s", unknown_err_msg)

            if reason:
                return self.async_abort(reason=reason)
            self.states = regions["states"]

        return await self._handle_pick_region("user", "district", user_input)

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
                CONF_REGION: self.selected_region["regionId"],
                CONF_NAME: self.selected_region["regionName"],
            },
        )


def _find(regions, region_id):
    return next((region for region in regions if region["regionId"] == region_id), None)


def _make_regions_object(regions):
    regions = sorted(regions, key=lambda region: region["regionName"].lower())
    return {region["regionId"]: region["regionName"] for region in regions}

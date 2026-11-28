"""Config flow for the Hydro-Québec Peak Events integration."""

from typing import Any, override

from hydropeak_opendata import OpenDataClient, OpenDataError, Sector
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.util import dt as dt_util

from .const import CONF_OFFER, DOMAIN


class HydroQuebecPeakConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydro-Québec Peak Events."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: pick the customer type."""
        return self.async_show_menu(
            step_id="user", menu_options=["residential", "business"]
        )

    async def async_step_residential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a residential offer."""
        return await self._async_step_offer(
            "residential", Sector.RESIDENTIAL, user_input
        )

    async def async_step_business(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a business offer."""
        return await self._async_step_offer("business", Sector.BUSINESS, user_input)

    async def _async_step_offer(
        self, step_id: str, sector: Sector, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Pick an offer of one customer type from the open data."""
        if user_input is not None:
            offer = user_input[CONF_OFFER]
            await self.async_set_unique_id(offer)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=offer, data={CONF_OFFER: offer})

        client = OpenDataClient(async_get_clientsession(self.hass))
        try:
            offers = await client.get_sector_offers(sector, dt_util.now().date())
        except OpenDataError:
            return self.async_abort(reason="cannot_connect")
        if not offers:
            return self.async_abort(reason="no_offers")

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_OFFER): SelectSelector(
                        SelectSelectorConfig(options=list(offers), sort=True)
                    )
                }
            ),
        )

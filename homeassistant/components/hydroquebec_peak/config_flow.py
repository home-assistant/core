"""Config flow for the Hydro-Québec Peak Events integration."""

from typing import Any, override

from hydropeak_opendata import OpenDataClient, OpenDataError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_OFFER, DOMAIN, LOGGER


class HydroQuebecPeakConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydro-Québec Peak Events."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: pick an offer from the live feed."""
        if user_input is not None:
            offer = user_input[CONF_OFFER]
            await self.async_set_unique_id(offer)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=offer, data={CONF_OFFER: offer})

        client = OpenDataClient(async_get_clientsession(self.hass))
        try:
            labels = await client.get_offer_labels()
        except OpenDataError as err:
            LOGGER.debug("Error fetching available offers: %s", err)
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OFFER): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=offer, label=label)
                                for offer, label in labels.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
        )

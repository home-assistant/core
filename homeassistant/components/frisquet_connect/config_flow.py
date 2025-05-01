import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from frisquet_connect.const import DOMAIN
from frisquet_connect.domains.exceptions.forbidden_access_exception import (
    ForbiddenAccessException,
)
from frisquet_connect.domains.site.site_light import SiteLight
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SELECTOR

from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    selector,
)

_LOGGER = logging.getLogger(__name__)


# https://developers.home-assistant.io/docs/data_entry_flow_index/
class FrisquetConnectFlow(ConfigFlow, domain=DOMAIN):

    VERSION = 1
    _user_input: dict = dict()

    def _get_sites(self) -> list[str]:
        return [str(site) for site in self._user_input["sites"]]

    def _get_vol_schema_for_authentication(self):
        return vol.Schema(
            {
                vol.Required(CONF_EMAIL): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.EMAIL, autocomplete="email"
                    )
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(
                        type=TextSelectorType.PASSWORD, autocomplete="current-password"
                    )
                ),
            }
        )

    def _get_vol_schema_for_site(self):
        return vol.Schema(
            {
                vol.Required(CONF_SELECTOR): selector(
                    {
                        "select": {
                            "options": self._get_sites(),
                        }
                    }
                )
            }
        )

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        # Ask for credentials if not already done
        if user_input is None:
            _LOGGER.info("Asking for authentication")
            return self.async_show_form(
                step_id="user", data_schema=self._get_vol_schema_for_authentication()
            )

        # Then update user_input
        self._user_input.update(user_input)

        # Finally, go to the next step
        try:
            return await self._set_auhentication_step()
        except Exception as e:
            _LOGGER.error(str(e))
            return self.async_abort(reason=str(e))

    async def _set_auhentication_step(self) -> FlowResult:
        # Get existing sites if not already done
        if self._user_input.get("sites") is None:
            service = FrisquetConnectDevice(
                self._user_input.get(CONF_EMAIL), self._user_input.get(CONF_PASSWORD)
            )
            try:
                authentication = await service.async_refresh_token_and_sites()
                self._user_input["sites"] = authentication.sites
            except ForbiddenAccessException:
                errors = {"base": "invalid_credentials"}
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_vol_schema_for_authentication(),
                    errors=errors,
                )

        # Finally, go to the next step
        return await self._set_site_step()

    async def _set_site_step(self) -> FlowResult:
        # No site so not possible to go further
        if len(self._user_input["sites"]) == 0:
            _LOGGER.error("No site found")
            return self.async_abort(reason="No site found")

        # Ask for site if not already done
        elif self._user_input.get(CONF_SELECTOR) is None:
            if len(self._user_input["sites"]) == 1:
                self._user_input[CONF_SELECTOR] = self._get_sites()[0]
            else:
                _LOGGER.info("Asking for site")
                return self.async_show_form(
                    step_id="user", data_schema=self._get_vol_schema_for_site()
                )

        site_selected: str = self._user_input[CONF_SELECTOR]
        site_light: SiteLight = next(
            site for site in self._user_input["sites"] if str(site) == site_selected
        )

        _LOGGER.debug(f"Setting unique id '{site_light.site_id}'")
        await self.async_set_unique_id(site_light.site_id)

        title = self._user_input[CONF_SELECTOR]
        data = {
            CONF_EMAIL: self._user_input[CONF_EMAIL],
            CONF_PASSWORD: self._user_input[CONF_PASSWORD],
            "site_id": site_light.site_id,
        }
        _LOGGER.info(f"Configuration completed: '{str(site_light)}'")
        return self.async_create_entry(title=title, data=data)

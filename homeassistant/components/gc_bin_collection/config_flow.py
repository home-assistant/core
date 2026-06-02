"""Config flow for Gold Coast Bin Collection."""

from typing import Any

from gcbinspy.gcbinspy import AddressException, GoldCoastBins
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_PROPERTY_ID, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
    }
)


class GCBinCollectionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gold Coast Bin Collection."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip()
            try:
                client: GoldCoastBins = await self.hass.async_add_executor_job(
                    GoldCoastBins, address
                )
                property_id: str = client.property_id()
            except AddressException:
                errors["base"] = "address_not_found"
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except requests.exceptions.Timeout:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(property_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=address,
                    data={
                        CONF_ADDRESS: address,
                        CONF_PROPERTY_ID: property_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA,
                user_input,
            ),
            errors=errors,
        )

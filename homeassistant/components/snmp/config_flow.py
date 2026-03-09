"""Config flow for SNMP.

A 'Config Flow' is a wizard that guides the user through setting up an integration
in the Home Assistant UI. It handles the input, validation, and creation of a 
'Config Entry' (a specific instance of this integration).
"""

from typing import Any

import voluptuous as vol

# ConfigFlow is the base class for all UI-based setup wizards.
# ConfigFlowResult is the type returned by the wizard steps.
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
)

# The 'Domain' is the unique identifier for the integration (e.g., 'snmp').
DOMAIN = "snmp"


class SnmpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SNMP.
    
    This class manages the lifecycle of the setup wizard.
    """

    # Version of the configuration data. If we change the data structure in the 
    # future, we would increment this and write a migration.
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step when a user clicks 'Add Integration' in the UI.
        
        If 'user_input' is None, we show the form.
        If 'user_input' has data, we process it and create the entry.
        """
        if user_input is not None:
            # If the user submitted the form, we create a 'Config Entry'.
            # 'title' is what appears in the list of integrations (usually the IP address or name).
            # 'data' is the actual configuration dictionary.
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        # 'async_show_form' displays a form in the UI.
        # 'data_schema' defines the fields the user needs to fill out.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    # vol.Required means the user MUST provide this.
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_BASEOID): str,
                    # vol.Optional provides a default value if left blank.
                    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
                    vol.Optional(CONF_AUTH_KEY): str,
                    vol.Optional(CONF_PRIV_KEY): str,
                }
            ),
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from the old YAML configuration file.
        
        This step is invisible to the user. It is triggered automatically when Home 
        Assistant finds old 'device_tracker: snmp' entries in configuration.yaml.
        """
        # We check the current list of 'Config Entries' to avoid creating duplicates.
        for entry in self._async_current_entries():
            # If an entry already exists with the same Host and BaseOID, we stop.
            if (
                entry.data.get(CONF_HOST) == user_input.get(CONF_HOST)
                and entry.data.get(CONF_BASEOID) == user_input.get(CONF_BASEOID)
            ):
                return self.async_abort(reason="already_configured")

        # If it's a new entry, we save it into the system's database.
        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

"""Config flow for Aarlo."""

import logging

import voluptuous as vol

from homeassistant import config_entries, exceptions

from .cfg import UpgradeCfg
from .const import *

_LOGGER = logging.getLogger(__name__)


class VirtualFlowHandler(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Aarlo config flow."""

    VERSION = 1

    async def validate_input(self, user_input):
        for group, values in self.hass.data.get(COMPONENT_DOMAIN, {}).items():
            _LOGGER.debug(f"checking {group}")
            if group == user_input[ATTR_GROUP_NAME]:
                raise GroupNameAlreadyUsed
            if values[ATTR_FILE_NAME] == user_input[ATTR_FILE_NAME]:
                raise FileNameAlreadyUsed
        return {"title": f"{user_input[ATTR_GROUP_NAME]} - {COMPONENT_DOMAIN}"}

    async def async_step_user(self, user_input):
        _LOGGER.debug(f"step user {user_input}")

        errors = {}
        if user_input is not None:
            try:
                info = await self.validate_input(user_input)
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        ATTR_GROUP_NAME: user_input[ATTR_GROUP_NAME],
                        ATTR_FILE_NAME: user_input[ATTR_FILE_NAME],
                    },
                )
            except GroupNameAlreadyUsed:
                errors["base"] = "group_name_used"
            except FileNameAlreadyUsed:
                errors["base"] = "file_name_used"

        else:
            # Fill in some defaults.
            user_input = {
                ATTR_GROUP_NAME: IMPORTED_GROUP_NAME,
                ATTR_FILE_NAME: IMPORTED_YAML_FILE,
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_GROUP_NAME, default=user_input[ATTR_GROUP_NAME]
                    ): str,
                    vol.Required(
                        ATTR_FILE_NAME, default=user_input[ATTR_FILE_NAME]
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data):
        """Import momentary config from configuration.yaml."""

        _LOGGER.debug(f"importing aarlo YAML {import_data}")
        UpgradeCfg.import_yaml(import_data)
        data = UpgradeCfg.create_flow_data(import_data)

        return self.async_create_entry(title="Imported Virtual Group", data=data)


class GroupNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating group name already used."""


class FileNameAlreadyUsed(exceptions.HomeAssistantError):
    """Error indicating file name already used."""

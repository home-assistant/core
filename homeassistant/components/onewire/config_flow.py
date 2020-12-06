"""Config flow for 1-Wire component."""
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.helpers.typing import HomeAssistantType

from .const import (  # pylint: disable=unused-import
    CONF_MOUNT_DIR,
    CONF_TYPE_OWFS,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_HOST,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from .onewirehub import CannotConnect, InvalidPath, OneWireHub

DATA_SCHEMA_USER = vol.Schema(
    {vol.Required(CONF_TYPE): vol.In([CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS])}
)
DATA_SCHEMA_OWSERVER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_OWSERVER_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_OWSERVER_PORT): int,
    }
)
DATA_SCHEMA_MOUNTDIR = vol.Schema(
    {
        vol.Required(CONF_MOUNT_DIR, default=DEFAULT_SYSBUS_MOUNT_DIR): str,
    }
)


async def validate_input_owserver(hass: HomeAssistantType, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA_OWSERVER with values provided by the user.
    """

    hub = OneWireHub(hass)

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    # Raises CannotConnect exception on failure
    await hub.connect(host, port)

    # Return info that you want to store in the config entry.
    return {"title": host}


def is_duplicate_owserver_entry(hass: HomeAssistantType, user_input):
    """Check existing entries for matching host and port."""
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if (
            config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER
            and config_entry.data[CONF_HOST] == user_input[CONF_HOST]
            and config_entry.data[CONF_PORT] == user_input[CONF_PORT]
        ):
            return True
    return False


async def validate_input_mount_dir(hass: HomeAssistantType, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA_MOUNTDIR with values provided by the user.
    """
    hub = OneWireHub(hass)

    mount_dir = data[CONF_MOUNT_DIR]

    # Raises InvalidDir exception on failure
    await hub.check_mount_dir(mount_dir)

    # Return info that you want to store in the config entry.
    return {"title": mount_dir}


class OneWireFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle 1-Wire config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize 1-Wire config flow."""
        self.onewire_config = {}

    async def async_step_user(self, user_input=None):
        """Handle 1-Wire config flow start.

        Let user manually input configuration.
        """
        errors = {}
        if user_input is not None:
            self.onewire_config.update(user_input)
            if CONF_TYPE_OWSERVER == user_input[CONF_TYPE]:
                return await self.async_step_owserver()
            if CONF_TYPE_SYSBUS == user_input[CONF_TYPE]:
                return await self.async_step_mount_dir()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    async def async_step_owserver(self, user_input=None):
        """Handle OWServer configuration."""
        errors = {}
        if user_input:
            # Prevent duplicate entries
            if is_duplicate_owserver_entry(self.hass, user_input):
                return self.async_abort(reason="already_configured")

            self.onewire_config.update(user_input)

            try:
                info = await validate_input_owserver(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=info["title"], data=self.onewire_config
                )

        return self.async_show_form(
            step_id="owserver",
            data_schema=DATA_SCHEMA_OWSERVER,
            errors=errors,
        )

    async def async_step_mount_dir(self, user_input=None):
        """Handle SysBus configuration."""
        errors = {}
        if user_input:
            # Prevent duplicate entries
            await self.async_set_unique_id(
                f"{CONF_TYPE_SYSBUS}:{user_input[CONF_MOUNT_DIR]}"
            )
            self._abort_if_unique_id_configured()

            self.onewire_config.update(user_input)

            try:
                info = await validate_input_mount_dir(self.hass, user_input)
            except InvalidPath:
                errors["base"] = "invalid_path"
            else:
                return self.async_create_entry(
                    title=info["title"], data=self.onewire_config
                )

        return self.async_show_form(
            step_id="mount_dir",
            data_schema=DATA_SCHEMA_MOUNTDIR,
            errors=errors,
        )

    async def async_step_import(self, platform_config):
        """Handle import configuration from YAML."""
        # OWServer
        if platform_config[CONF_TYPE] == CONF_TYPE_OWSERVER:
            if CONF_PORT not in platform_config:
                platform_config[CONF_PORT] = DEFAULT_OWSERVER_PORT
            return await self.async_step_owserver(platform_config)

        # OWFS
        if platform_config[CONF_TYPE] == CONF_TYPE_OWFS:  # pragma: no cover
            # This part of the implementation does not conform to policy regarding 3rd-party libraries, and will not longer be updated.
            # https://developers.home-assistant.io/docs/creating_platform_code_review/#5-communication-with-devicesservices
            await self.async_set_unique_id(
                f"{CONF_TYPE_OWFS}:{platform_config[CONF_MOUNT_DIR]}"
            )
            self._abort_if_unique_id_configured(
                updates=platform_config, reload_on_update=True
            )
            return self.async_create_entry(
                title=platform_config[CONF_MOUNT_DIR], data=platform_config
            )

        # SysBus
        if CONF_MOUNT_DIR not in platform_config:
            platform_config[CONF_MOUNT_DIR] = DEFAULT_SYSBUS_MOUNT_DIR
        return await self.async_step_mount_dir(platform_config)

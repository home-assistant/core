"""Config flow for UniFi AP Direct integration."""

from typing import Any, override

from unifi_ap import UniFiAP, UniFiAPConnectionException, UniFiAPDataException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers import selector

from .const import DEFAULT_NAME, DEFAULT_SSH_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOSTS): selector.ObjectSelector(
            selector.ObjectSelectorConfig(
                multiple=True,
                fields={
                    CONF_HOST: {
                        "selector": selector.TextSelector(selector.TextSelectorConfig())
                    },
                    CONF_USERNAME: {
                        "selector": selector.TextSelector(selector.TextSelectorConfig())
                    },
                    CONF_PASSWORD: {
                        "selector": selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        )
                    },
                    CONF_PORT: {
                        "selector": selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=65535,
                                mode=selector.NumberSelectorMode.BOX,
                            )
                        )
                    },
                },
            )
        )
    }
)


def _get_host_configs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return configured hosts from the config entry."""
    host_entries = data.get(CONF_HOSTS, [])

    host_configs: list[dict[str, Any]] = []
    for entry in host_entries:
        if not isinstance(entry, dict):
            continue

        host = entry.get(CONF_HOST)
        if not host:
            continue

        host_configs.append(
            {
                CONF_HOST: str(host),
                CONF_USERNAME: entry.get(CONF_USERNAME, ""),
                CONF_PASSWORD: entry.get(CONF_PASSWORD, ""),
                CONF_PORT: entry.get(CONF_PORT, DEFAULT_SSH_PORT),
            }
        )

    return host_configs


def validate_connection_data(data: dict[str, Any]) -> None:
    """Validate that we can connect to the UniFi AP with the provided configuration."""
    try:
        for host_config in _get_host_configs(data):
            ap = UniFiAP(
                target=host_config[CONF_HOST],
                username=host_config[CONF_USERNAME],
                password=host_config[CONF_PASSWORD],
                port=host_config[CONF_PORT],
            )
            ap.get_clients()
    except (UniFiAPConnectionException, UniFiAPDataException) as err:
        raise CannotConnect("Failed to connect to UniFi AP") from err


class UniFiDirectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Direct."""

    VERSION = 2
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host_configs = _get_host_configs(user_input)
            if not host_configs:
                errors["base"] = "cannot_connect"
            else:
                entry_data = {CONF_HOSTS: host_configs}
                self._async_abort_entries_match(entry_data)
                try:
                    await self.hass.async_add_executor_job(
                        validate_connection_data, entry_data
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"{DEFAULT_NAME} ({', '.join(host[CONF_HOST] for host in host_configs)})",
                        data=entry_data,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import existing config from configuration.yaml."""
        host_config = {
            CONF_HOST: import_data.get(CONF_HOST),
            CONF_USERNAME: import_data.get(CONF_USERNAME, ""),
            CONF_PASSWORD: import_data.get(CONF_PASSWORD, ""),
            CONF_PORT: import_data.get(CONF_PORT, DEFAULT_SSH_PORT),
        }

        if not host_config[CONF_HOST]:
            return self.async_abort(reason="cannot_connect")

        entry_data = {CONF_HOSTS: [host_config]}
        self._async_abort_entries_match(entry_data)

        try:
            await self.hass.async_add_executor_job(validate_connection_data, entry_data)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({host_config[CONF_HOST]})",
            data=entry_data,
        )


class CannotConnect(Exception):
    """Custom exception for failing to connect to the UniFiAP."""

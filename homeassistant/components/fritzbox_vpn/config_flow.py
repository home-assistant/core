"""Config flow for FritzBox VPN integration."""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ERROR_KEY_CANNOT_CONNECT,
    ERROR_KEY_CONFIG_ENTRY_NOT_FOUND,
    ERROR_KEY_INVALID_AUTH,
    ERROR_KEY_UNKNOWN,
    OPTIONS_ACTION_CLEANUP,
    OPTIONS_ACTION_CONFIGURE,
    OPTIONS_ACTION_REPAIR_ENTITY_IDS,
    host_from_config,
    password_from_sources,
)
from .coordinator import normalize_update_interval
from .entity_registry import (
    get_entity_id_suffix_repairs,
    get_orphaned_entity_entries,
    remove_orphaned_entities,
    repair_entity_id_suffixes,
)
from .flow_forms import (
    CannotConnect,
    InvalidAuth,
    configure_schema,
    confirm_checkbox_schema,
    confirm_schema,
    credentials_defaults,
    credentials_schema,
    fill_password_if_missing,
    reauth_schema,
    set_validation_error,
    validate_host_on_submit,
    validate_input,
)
from .fritz_config_source import get_existing_fritz_config
from .ssdp_unique_id import (
    host_from_ssdp,
    is_fritzbox_router_discovery,
    unique_id_for_discovery,
)

_LOGGER = logging.getLogger(__name__)

OPTIONS_LABEL_CONFIGURE = "Configure (host, user, update interval)"
OPTIONS_LABEL_CLEANUP = "Remove unavailable entities"
OPTIONS_LABEL_REPAIR_ENTITY_IDS = "Repair entity IDs"


async def _try_create_entry_from_credentials(
    flow: config_entries.ConfigFlow,
    hass: HomeAssistant,
    user_input: dict[str, Any],
    errors: dict[str, str],
    *,
    password_sources: tuple[Mapping[str, Any] | None, ...],
    unique_id: str | None,
    log_unknown_details: bool,
) -> FlowResult | None:
    """Validate credentials and create entry; None if the form should be shown again."""
    fill_password_if_missing(user_input, *password_sources)
    if not validate_host_on_submit(user_input, errors):
        return None
    try:
        info = await validate_input(hass, user_input)
    except Exception as err:
        set_validation_error(errors, err, log_unknown_details=log_unknown_details)
        return None
    await flow.async_set_unique_id(unique_id or user_input.get(CONF_HOST))
    flow._abort_if_unique_id_configured()
    return flow.async_create_entry(title=info["title"], data=user_input)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FritzBox VPN."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_unique_id: str | None = None
        self._existing_config: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is None:
            self._existing_config = await get_existing_fritz_config(self.hass)
            if self._existing_config:
                has_host = bool(self._existing_config.get(CONF_HOST))
                has_username = bool(self._existing_config.get(CONF_USERNAME))
                has_password = bool(password_from_sources(self._existing_config))
                if has_host and has_username and has_password:
                    try:
                        info = await validate_input(self.hass, self._existing_config)
                        host = self._existing_config.get(CONF_HOST)
                        await self.async_set_unique_id(host)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=info["title"], data=self._existing_config
                        )
                    except CannotConnect:
                        _LOGGER.warning(
                            "Autoconfiguration connection test failed: %s",
                            ERROR_KEY_CANNOT_CONNECT,
                        )
                        errors["base"] = ERROR_KEY_CANNOT_CONNECT
                    except InvalidAuth:
                        _LOGGER.warning(
                            "Autoconfiguration connection test failed: %s",
                            ERROR_KEY_INVALID_AUTH,
                        )
                        errors["base"] = ERROR_KEY_INVALID_AUTH
                    except Exception as err:
                        _LOGGER.warning(
                            "Autoconfiguration connection test failed: %s", err
                        )
                        errors["base"] = ERROR_KEY_UNKNOWN
            schema = credentials_schema(*credentials_defaults(self._existing_config))
            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        result = await _try_create_entry_from_credentials(
            self,
            self.hass,
            user_input,
            errors,
            password_sources=(self._existing_config,),
            unique_id=user_input.get(CONF_HOST),
            log_unknown_details=True,
        )
        if result is not None:
            return result
        schema = credentials_schema(*credentials_defaults(user_input))
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery (fallback if no existing integration found)."""
        existing_config = await get_existing_fritz_config(self.hass)
        if existing_config:
            return self.async_abort(reason="already_configured")

        if not is_fritzbox_router_discovery(discovery_info):
            return self.async_abort(reason="not_fritzbox")

        host = host_from_ssdp(discovery_info)
        if not host:
            return self.async_abort(reason="no_host")
        try:
            if ipaddress.ip_address(host).is_link_local:
                return self.async_abort(reason="no_host")
        except ValueError:
            pass

        unique_id = unique_id_for_discovery(discovery_info, host)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovered_host = host
        self._discovered_unique_id = unique_id
        self.context["title_placeholders"] = {"host": host}
        self._existing_config = await get_existing_fritz_config(self.hass)
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=confirm_schema(self._existing_config, self._discovered_host),
                description_placeholders={"host": self._discovered_host or DEFAULT_HOST},
            )

        result = await _try_create_entry_from_credentials(
            self,
            self.hass,
            user_input,
            errors,
            password_sources=(self._existing_config,),
            unique_id=self._discovered_unique_id,
            log_unknown_details=False,
        )
        if result is not None:
            return result
        return self.async_show_form(
            step_id="confirm",
            data_schema=confirm_schema(
                self._existing_config,
                self._discovered_host,
                current_input=user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle reauthentication after invalid credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update credentials after authentication failure."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        host = host_from_config(reauth_entry.data)
        username_default = reauth_entry.data.get(CONF_USERNAME, "")

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=reauth_schema(username_default),
                description_placeholders={"host": host},
                errors=errors,
            )

        credentials = {
            CONF_HOST: host,
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        try:
            await validate_input(self.hass, credentials)
        except Exception as err:
            set_validation_error(errors, err, log_unknown_details=True)
        else:
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={
                    **reauth_entry.data,
                    CONF_HOST: host,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema(
                user_input.get(CONF_USERNAME, username_default)
            ),
            description_placeholders={"host": host},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for FritzBox VPN."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry

    def _get_current_entry(self) -> config_entries.ConfigEntry | None:
        return self.hass.config_entries.async_get_entry(self._config_entry.entry_id)

    def _get_available_actions(self) -> tuple[bool, bool, int]:
        """Return (has_cleanup_action, has_repair_action, repair_count)."""
        try:
            to_remove, error_key = get_orphaned_entity_entries(
                self.hass, self._config_entry.entry_id
            )
            registry = er.async_get(self.hass)
            repairs = get_entity_id_suffix_repairs(
                registry, self._config_entry.entry_id
            )
            has_cleanup_action = error_key is None and bool(to_remove)
            has_repair_action = bool(repairs)
            return (has_cleanup_action, has_repair_action, len(repairs))
        except Exception as err:
            _LOGGER.exception(
                "Failed to evaluate available options actions for entry %s: %s",
                self._config_entry.entry_id,
                err,
            )
            return (False, False, 0)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options menu: configure, cleanup, or repair entity ID suffixes."""
        has_cleanup_action, has_repair_action, _ = self._get_available_actions()
        has_extra_actions = has_cleanup_action or has_repair_action

        if user_input is None and not has_extra_actions:
            return await self.async_step_configure()

        if user_input is not None:
            if user_input.get("action") == OPTIONS_ACTION_CLEANUP:
                return await self.async_step_cleanup_confirm()
            if user_input.get("action") == OPTIONS_ACTION_REPAIR_ENTITY_IDS:
                return await self.async_step_repair_entity_ids_confirm()
            return await self.async_step_configure()

        choices = {OPTIONS_ACTION_CONFIGURE: OPTIONS_LABEL_CONFIGURE}
        if has_cleanup_action:
            choices[OPTIONS_ACTION_CLEANUP] = OPTIONS_LABEL_CLEANUP
        if has_repair_action:
            choices[OPTIONS_ACTION_REPAIR_ENTITY_IDS] = OPTIONS_LABEL_REPAIR_ENTITY_IDS
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default=OPTIONS_ACTION_CONFIGURE): vol.In(
                        choices
                    ),
                }
            ),
        )

    async def _confirm_options_action(
        self,
        *,
        step_id: str,
        entry_id: str,
        user_input: dict[str, Any] | None,
        pending: list[Any],
        on_confirm,
    ) -> FlowResult:
        """Shared confirm step for cleanup and entity-ID repair."""
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)

        if user_input is not None and user_input.get("confirm") and pending:
            await on_confirm(entry_id)
            return self.async_create_entry(title="", data=config_entry.options or {})

        if user_input is not None or not pending:
            return self.async_create_entry(title="", data=config_entry.options or {})

        return self.async_show_form(
            step_id=step_id,
            data_schema=confirm_checkbox_schema(),
        )

    async def async_step_cleanup_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm removal of entities for VPN connections no longer on the Fritz!Box."""
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)
        entry_id = config_entry.entry_id
        to_remove, error_key = get_orphaned_entity_entries(self.hass, entry_id)
        if error_key is not None:
            return self.async_show_form(
                step_id="cleanup_confirm",
                data_schema=vol.Schema({}),
                errors={"base": error_key},
            )

        async def on_cleanup(confirmed_entry_id: str) -> None:
            remove_orphaned_entities(self.hass, confirmed_entry_id, to_remove or [])
            await self.hass.config_entries.async_reload(confirmed_entry_id)

        return await self._confirm_options_action(
            step_id="cleanup_confirm",
            entry_id=entry_id,
            user_input=user_input,
            pending=to_remove or [],
            on_confirm=on_cleanup,
        )

    async def async_step_repair_entity_ids_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm repair of entity IDs (_2, _3, … → base ID)."""
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)
        entry_id = config_entry.entry_id
        registry = er.async_get(self.hass)
        repairs = get_entity_id_suffix_repairs(registry, entry_id)

        async def on_repair(confirmed_entry_id: str) -> None:
            count, _ = repair_entity_id_suffixes(self.hass, confirmed_entry_id)
            if count:
                await self.hass.config_entries.async_reload(confirmed_entry_id)

        return await self._confirm_options_action(
            step_id="repair_entity_ids_confirm",
            entry_id=entry_id,
            user_input=user_input,
            pending=repairs,
            on_confirm=on_repair,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        config_entry = self._get_current_entry()
        if not config_entry:
            return self.async_abort(reason=ERROR_KEY_CONFIG_ENTRY_NOT_FOUND)

        if user_input is not None:
            user_input = dict(user_input)
            user_input.pop("action", None)
            fill_password_if_missing(user_input, config_entry.data or {})
            if not validate_host_on_submit(user_input, errors):
                return self.async_show_form(
                    step_id="configure",
                    data_schema=configure_schema(
                        user_input, config_entry.options or {}
                    ),
                    errors=errors,
                )
            try:
                await validate_input(self.hass, user_input)
            except Exception as err:
                set_validation_error(errors, err, log_unknown_details=True)
            else:
                config_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                update_interval = normalize_update_interval(
                    user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                )
                options_data = {CONF_UPDATE_INTERVAL: update_interval}
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data=config_data,
                    options=options_data,
                )
                result = self.async_create_entry(title="", data=options_data)
                await self.hass.config_entries.async_reload(config_entry.entry_id)
                return result

        return self.async_show_form(
            step_id="configure",
            data_schema=configure_schema(
                config_entry.data or {}, config_entry.options or {}
            ),
            errors=errors,
        )

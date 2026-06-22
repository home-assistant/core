"""Config flow for Bosch Smart Home Controller integration."""

from os import makedirs
from typing import Any

import voluptuous as vol
from boschshcpy import SHCRegisterClient, SHCSession
from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCRegistrationError,
    SHCSessionError,
)
from homeassistant import config_entries, core
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_HOSTNAME,
    CONF_SHC_CERT,
    CONF_SHC_KEY,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DATA_SESSION,
    DOMAIN,
    LOGGER,
    OPT_CHILD_LOCK_ENABLED,
    OPT_DIAGNOSTIC_ENTITIES,
    OPT_ENABLE_RAWSCAN,
    OPT_EXCLUDED_DEVICES,
    OPT_EXCLUDED_ROOMS,
    OPT_LONG_POLL_TIMEOUT,
    OPT_PRESENCE_ENTITY,
    OPT_SCENARIOS_AS_BUTTONS,
    OPT_SSL_VERIFY_HOSTNAME,
    OPT_SSL_SKIP_VERIFY,
    OPT_SILENT_MODE_ENABLED,
    OPT_SILENT_MODE_START,
    OPT_SILENT_MODE_END,
)

# ── Section layout (single source of truth) ──────────────────────────────────
# Maps each section key to the flat OPT_* keys it contains.
# _flatten_sections() uses this to lift nested section dicts back to the flat
# shape that the rest of the integration (sensor.py, __init__.py) expects.
OPTIONS_SECTIONS: dict[str, list[str]] = {
    "features": [
        OPT_SCENARIOS_AS_BUTTONS,
        OPT_DIAGNOSTIC_ENTITIES,
        OPT_ENABLE_RAWSCAN,
    ],
    "presence": [
        OPT_CHILD_LOCK_ENABLED,
        OPT_PRESENCE_ENTITY,
        OPT_SILENT_MODE_ENABLED,
        OPT_SILENT_MODE_START,
        OPT_SILENT_MODE_END,
    ],
    "advanced": [
        OPT_SSL_VERIFY_HOSTNAME,
        OPT_SSL_SKIP_VERIFY,
        OPT_LONG_POLL_TIMEOUT,
        OPT_EXCLUDED_DEVICES,
        OPT_EXCLUDED_ROOMS,
    ],
}


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten section-grouped submit dict back to a single flat dict.

    HA's section() helper returns nested input in the shape
    {section_key: {field: value, ...}, ...}.  This helper lifts every nested
    field up to the top level so the rest of the integration keeps reading
    flat OPT_* keys unchanged.

    Non-sectioned keys (e.g. from older tests or programmatic updates)
    pass through unchanged.  Duplicate keys raise ValueError.
    """
    flat: dict[str, Any] = {}
    seen_section_keys: set[str] = set()

    for section_key, _fields in OPTIONS_SECTIONS.items():
        seen_section_keys.add(section_key)
        sec_payload = user_input.get(section_key)
        if sec_payload is None or not isinstance(sec_payload, dict):
            continue
        for field, value in sec_payload.items():
            if field in flat:
                raise ValueError(
                    f"_flatten_sections: duplicate key {field!r} from "
                    f"section {section_key!r}"
                )
            flat[field] = value

    for key, value in user_input.items():
        if key in seen_section_keys:
            continue
        if key in flat:
            raise ValueError(
                f"_flatten_sections: duplicate key {key!r} at top level and inside a section"
            )
        flat[key] = value

    return flat


HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
    }
)


def write_tls_asset(hass: core.HomeAssistant, filename: str, asset: bytes) -> None:
    """Write the tls assets to disk."""
    makedirs(hass.config.path(DOMAIN), exist_ok=True)
    with open(hass.config.path(DOMAIN, filename), "w", encoding="utf8") as file_handle:
        file_handle.write(asset.decode("utf-8"))


def create_credentials_and_validate(hass, host, user_input, zeroconf_instance):
    """Create and store credentials and validate session."""
    helper = SHCRegisterClient(host, user_input[CONF_PASSWORD])
    result = helper.register(user_input[CONF_NAME].lower(), user_input[CONF_NAME])

    if result is not None:
        hostname = result["token"].split(":", 1)[1]
        write_tls_asset(hass, CONF_SHC_CERT + "_" + hostname + ".pem", result["cert"])
        write_tls_asset(hass, CONF_SHC_KEY + "_" + hostname + ".pem", result["key"])

        session = SHCSession(
            host,
            hass.config.path(DOMAIN, CONF_SHC_CERT + "_" + hostname + ".pem"),
            hass.config.path(DOMAIN, CONF_SHC_KEY + "_" + hostname + ".pem"),
            True,
            zeroconf_instance,
        )
        session.authenticate()

    return result


def get_info_from_host(hass, host, zeroconf_instance):
    """Get information from host."""
    session = SHCSession(
        host,
        "",
        "",
        True,
        zeroconf_instance,
    )
    information = session.mdns_info()
    return {"title": information.name, "unique_id": information.unique_id}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch SHC."""

    VERSION = 1
    info = None
    host = None
    hostname = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=HOST_SCHEMA,
            )
        self.host = host = user_input[CONF_HOST]
        self.info = await self._get_info(host)
        return await self.async_step_credentials()

    async def async_step_reconfigure(self, user_input=None):
        """Show a menu: change host only, or re-pair (regenerate certificate)."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["reconfigure_host", "repair_credentials"],
        )

    async def async_step_reconfigure_host(self, user_input=None):
        """Allow the user to change the SHC host/IP without re-pairing."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            new_host = user_input[CONF_HOST]
            try:
                info = await self._get_info(new_host)
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception during reconfigure_host")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_shc")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: new_host},
                )

        return self.async_show_form(
            step_id="reconfigure_host",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data.get(CONF_HOST, "")
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_repair_credentials(self, user_input=None):
        """Re-pair: regenerate the client certificate/key for this SHC entry."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            zeroconf_instance = await zeroconf.async_get_instance(self.hass)
            try:
                result = await self.hass.async_add_executor_job(
                    create_credentials_and_validate,
                    self.hass,
                    host,
                    user_input,
                    zeroconf_instance,
                )
            except SHCAuthenticationError:
                errors["base"] = "invalid_auth"
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except SHCSessionError as err:
                LOGGER.warning("Session error: %s", err.message)
                errors["base"] = "session_error"
            except SHCRegistrationError as err:
                LOGGER.warning("Registration error: %s", err.message)
                errors["base"] = "pairing_failed"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception during repair_credentials")
                errors["base"] = "unknown"
            else:
                hostname = result["token"].split(":", 1)[1]
                new_entry_data = {
                    CONF_SSL_CERTIFICATE: self.hass.config.path(
                        DOMAIN, CONF_SHC_CERT + "_" + hostname + ".pem"
                    ),
                    CONF_SSL_KEY: self.hass.config.path(
                        DOMAIN, CONF_SHC_KEY + "_" + hostname + ".pem"
                    ),
                    CONF_HOST: host,
                    CONF_TOKEN: result["token"],
                    CONF_HOSTNAME: hostname,
                }
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_entry_data,
                )

        current_host = entry.data.get(CONF_HOST, "")
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=current_host
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    CONF_NAME, default="HomeAssistant"
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

        return self.async_show_form(
            step_id="repair_credentials",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                self.info = info = await self._get_info(host)
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured({CONF_HOST: host})
                self.host = host
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user", data_schema=HOST_SCHEMA, errors=errors
        )

    async def async_step_credentials(self, user_input=None):
        """Handle the credentials step."""
        errors = {}
        if user_input is not None:
            zeroconf_instance = await zeroconf.async_get_instance(self.hass)
            try:
                result = await self.hass.async_add_executor_job(
                    create_credentials_and_validate,
                    self.hass,
                    self.host,
                    user_input,
                    zeroconf_instance,
                )
            except SHCAuthenticationError:
                errors["base"] = "invalid_auth"
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except SHCSessionError as err:
                LOGGER.warning("Session error: %s", err.message)
                errors["base"] = "session_error"
            except SHCRegistrationError as err:
                LOGGER.warning("Registration error: %s", err.message)
                errors["base"] = "pairing_failed"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                hostname = result["token"].split(":", 1)[1]
                entry_data = {
                    CONF_SSL_CERTIFICATE: self.hass.config.path(
                        DOMAIN, CONF_SHC_CERT + "_" + hostname + ".pem"
                    ),
                    CONF_SSL_KEY: self.hass.config.path(
                        DOMAIN, CONF_SHC_KEY + "_" + hostname + ".pem"
                    ),
                    CONF_HOST: self.host,
                    CONF_TOKEN: result["token"],
                    CONF_HOSTNAME: hostname,
                }
                existing_entry = await self.async_set_unique_id(self.info["unique_id"])
                if existing_entry:
                    return self.async_update_reload_and_abort(
                        existing_entry,
                        data=entry_data,
                    )

                return self.async_create_entry(
                    title=self.info["title"],
                    data=entry_data,
                )
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(
                    CONF_NAME, default=user_input.get(CONF_NAME, "HomeAssistant")
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        if not discovery_info.name.startswith("Bosch SHC"):
            return self.async_abort(reason="not_bosch_shc")

        try:
            self.info = await self._get_info(discovery_info.host)
        except SHCConnectionError:
            return self.async_abort(reason="cannot_connect")
        self.host = discovery_info.host

        local_name = discovery_info.hostname[:-1]
        node_name = local_name[: -len(".local")]

        await self.async_set_unique_id(self.info["unique_id"])
        self._abort_if_unique_id_configured({CONF_HOST: self.host})
        self.context["title_placeholders"] = {"name": node_name}
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(self, user_input=None):
        """Handle discovery confirm."""
        errors = {}
        if user_input is not None:
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "model": "Bosch SHC",
                "host": self.host,
            },
            errors=errors,
        )

    async def _get_info(self, host):
        """Get additional information."""
        zeroconf_instance = await zeroconf.async_get_instance(self.hass)

        return await self.hass.async_add_executor_job(
            get_info_from_host,
            self.hass,
            host,
            zeroconf_instance,
        )


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options flow for Bosch SHC."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # HA's section() nests fields; flatten back to the flat OPT_* shape
            # that sensor.py, __init__.py, etc. read.
            flat = _flatten_sections(user_input)
            return self.async_create_entry(title="", data=flat)

        current = self.config_entry.options

        # The presence entity option became multi-select; existing entries may
        # still hold a single entity id as a plain string. Coerce to a list so
        # the multiple=True EntitySelector never receives a string (which makes
        # the frontend ha-entities-picker crash with "t.map is not a function").
        _presence_default = current.get(OPT_PRESENCE_ENTITY, [])
        if isinstance(_presence_default, str):
            _presence_default = [_presence_default] if _presence_default else []

        # Build device/room option lists from the live session.
        device_options = []
        room_options = []
        try:
            data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if data:
                session = data[DATA_SESSION]
                rooms = {r.id: r.name for r in session.rooms}
                for dev in session.devices:
                    room_name = rooms.get(getattr(dev, "room_id", None), "")
                    label = (
                        f"{dev.name} ({room_name})" if room_name else dev.name
                    )
                    device_options.append({"value": dev.id, "label": label})
                room_options = [
                    {"value": rid, "label": name}
                    for rid, name in rooms.items()
                ]
        except Exception:  # never break the options flow if session is unavailable
            LOGGER.debug(
                "Could not build device/room filter options", exc_info=True
            )

        schema = vol.Schema(
            {
                vol.Required("features"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                OPT_SCENARIOS_AS_BUTTONS,
                                default=current.get(OPT_SCENARIOS_AS_BUTTONS, False),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_DIAGNOSTIC_ENTITIES,
                                default=current.get(OPT_DIAGNOSTIC_ENTITIES, True),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_ENABLE_RAWSCAN,
                                default=current.get(OPT_ENABLE_RAWSCAN, True),
                            ): BooleanSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("presence"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                OPT_CHILD_LOCK_ENABLED,
                                default=current.get(
                                    OPT_CHILD_LOCK_ENABLED, bool(_presence_default)
                                ),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_PRESENCE_ENTITY,
                                default=_presence_default,
                            ): EntitySelector(
                                EntitySelectorConfig(
                                    multiple=True,
                                    domain=[
                                        "person",
                                        "device_tracker",
                                        "binary_sensor",
                                        "input_boolean",
                                        "zone",
                                        "group",
                                    ],
                                )
                            ),
                            vol.Optional(
                                OPT_SILENT_MODE_ENABLED,
                                default=current.get(
                                    OPT_SILENT_MODE_ENABLED, False
                                ),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_SILENT_MODE_START,
                                default=current.get(
                                    OPT_SILENT_MODE_START, "22:00:00"
                                ),
                            ): TimeSelector(),
                            vol.Optional(
                                OPT_SILENT_MODE_END,
                                default=current.get(
                                    OPT_SILENT_MODE_END, "06:00:00"
                                ),
                            ): TimeSelector(),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("advanced"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                OPT_SSL_VERIFY_HOSTNAME,
                                default=current.get(OPT_SSL_VERIFY_HOSTNAME, False),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_SSL_SKIP_VERIFY,
                                default=current.get(OPT_SSL_SKIP_VERIFY, False),
                            ): BooleanSelector(),
                            vol.Optional(
                                OPT_LONG_POLL_TIMEOUT,
                                default=current.get(OPT_LONG_POLL_TIMEOUT, 10),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=5,
                                    max=60,
                                    step=1,
                                    unit_of_measurement="s",
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                            vol.Optional(
                                OPT_EXCLUDED_DEVICES,
                                default=current.get(OPT_EXCLUDED_DEVICES, []),
                            ): (
                                SelectSelector(
                                    SelectSelectorConfig(
                                        options=device_options,
                                        multiple=True,
                                        mode=SelectSelectorMode.DROPDOWN,
                                        custom_value=False,
                                        sort=True,
                                    )
                                )
                                if device_options
                                else vol.Schema(vol.All(list, [str]))
                            ),
                            vol.Optional(
                                OPT_EXCLUDED_ROOMS,
                                default=current.get(OPT_EXCLUDED_ROOMS, []),
                            ): (
                                SelectSelector(
                                    SelectSelectorConfig(
                                        options=room_options,
                                        multiple=True,
                                        mode=SelectSelectorMode.DROPDOWN,
                                        custom_value=False,
                                        sort=True,
                                    )
                                )
                                if room_options
                                else vol.Schema(vol.All(list, [str]))
                            ),
                        }
                    ),
                    {"collapsed": False},
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

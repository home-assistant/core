"""Config flow for the JFL Alarm integration.

The panel introduces itself when it dials in, so the only thing worth asking for is the port the
integration listens on. Panels then arrive on their own as subentries; the manual subentry step
exists for an installation whose panel is not powered yet.

`async_set_unique_id(str(port))` makes the port the entry's identity: two listeners cannot share one
port, and two on different ports are a legitimate setup.
"""

from typing import TYPE_CHECKING, Any, override

from pyjfl import check_port_available
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_READ_ONLY,
    CONF_SERIAL,
    DEFAULT_CODE,
    DEFAULT_CODE_ARM_REQUIRED,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_READ_ONLY,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PANEL,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from . import JflConfigEntry


def _hub_schema(host: str, port: int) -> vol.Schema:
    """Build the schema for the listening address and port."""
    return vol.Schema(
        {
            vol.Required(CONF_PORT, default=port): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_HOST, default=host): TextSelector(),
        }
    )


class JflConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the listener."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the port to listen on and confirm nothing else holds it."""
        host = DEFAULT_HOST
        port = DEFAULT_PORT
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip() or DEFAULT_HOST
            port = int(user_input[CONF_PORT])
            await self.async_set_unique_id(str(port))
            self._abort_if_unique_id_configured()
            try:
                await self.hass.async_add_executor_job(check_port_available, host, port)
            except OSError as err:
                LOGGER.debug("cannot bind %s:%s: %s", host, port, err)
                errors["base"] = "port_in_use"
            else:
                return self.async_create_entry(
                    title=f"JFL Alarm ({port})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user", data_schema=_hub_schema(host, port), errors=errors
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """One subentry type: a panel."""
        return {SUBENTRY_TYPE_PANEL: JflPanelSubentryFlow}


class JflPanelSubentryFlow(ConfigSubentryFlow):
    """Add or edit one panel.

    Adding a panel by hand is normally unnecessary: the listener creates the subentry when the panel
    dials in. This flow exists for an installation whose panel is not powered yet, and to edit the
    settings of a panel that was added automatically.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Take a panel's serial by hand."""
        entry: JflConfigEntry = self._get_entry()
        errors: dict[str, str] = {}
        known = {
            subentry.unique_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_PANEL
        }

        if user_input is not None:
            serial = str(user_input[CONF_SERIAL]).strip()
            if not serial:
                errors[CONF_SERIAL] = "invalid_serial"
            elif serial in known:
                return self.async_abort(reason="already_configured")
            else:
                return self.async_create_entry(
                    title=f"JFL panel {serial}",
                    data={
                        CONF_SERIAL: serial,
                        CONF_READ_ONLY: bool(user_input[CONF_READ_ONLY]),
                        **_code_settings(user_input),
                    },
                    unique_id=serial,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL): TextSelector(),
                vol.Required(CONF_READ_ONLY, default=DEFAULT_READ_ONLY): bool,
                vol.Optional(CONF_CODE, default=DEFAULT_CODE): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_CODE_ARM_REQUIRED, default=DEFAULT_CODE_ARM_REQUIRED
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change one panel's settings. The serial is its identity and is not editable."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                entry,
                subentry,
                data_updates={
                    CONF_READ_ONLY: bool(user_input[CONF_READ_ONLY]),
                    **_code_settings(user_input),
                },
            )

        data: Mapping[str, Any] = subentry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_READ_ONLY, default=data.get(CONF_READ_ONLY, DEFAULT_READ_ONLY)
                ): bool,
                vol.Optional(
                    CONF_CODE, default=data.get(CONF_CODE, DEFAULT_CODE)
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Required(
                    CONF_CODE_ARM_REQUIRED,
                    default=data.get(CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED),
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            description_placeholders={
                CONF_SERIAL: str(subentry.data.get(CONF_SERIAL, ""))
            },
        )


def _code_settings(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise the optional arm/disarm code out of a submitted form.

    The code is a Home Assistant code and never reaches the panel. With no code set, requiring it to
    arm is meaningless and is stored as `False`.
    """
    code = str(user_input.get(CONF_CODE, DEFAULT_CODE) or "").strip()
    return {
        CONF_CODE: code,
        CONF_CODE_ARM_REQUIRED: bool(code)
        and bool(user_input.get(CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED)),
    }

"""Configuration flows: the listener, its panels, and their options.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

**The user is asked for as little as possible, because nearly everything is detectable.** The panel
introduces itself when it dials in: serial, model, firmware, MAC, how many partitions are
programmed, whether an electric fence exists, which zones are in use. None of that is worth asking.

What cannot be detected is the **port**, and only because it is the wrong way round: the installer
programs a destination into the panel, and the integration has to be listening on whatever they
chose. So the hub step asks for a port and a bind address and nothing else.

Panels then arrive on their own. The default unknown-panel policy is *accept*, so a panel that dials
in becomes a subentry with no user action at all; the manual path exists for an installation where
the panel is not powered yet, and the *hold* policy for someone who wants to approve each one.

`async_set_unique_id(str(port))` makes the port the entry's identity: two listeners on one port
cannot work, and two on different ports are a legitimate setup.
"""

from typing import TYPE_CHECKING, Any, override

from pyjfl import check_port_available
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CODE,
    CONF_CODE_ARM_REQUIRED,
    CONF_KEEPALIVE_MINUTES,
    CONF_LOG_RAW_FRAMES,
    CONF_PROGRAMMING_READ_INTERVAL,
    CONF_READ_ONLY,
    CONF_SERIAL,
    CONF_UNKNOWN_PANELS,
    DEFAULT_CODE,
    DEFAULT_CODE_ARM_REQUIRED,
    DEFAULT_HOST,
    DEFAULT_KEEPALIVE_MINUTES,
    DEFAULT_LOG_RAW_FRAMES,
    DEFAULT_PORT,
    DEFAULT_PROGRAMMING_READ_INTERVAL,
    DEFAULT_READ_ONLY,
    DEFAULT_UNKNOWN_PANELS,
    DOMAIN,
    LOGGER,
    MAX_KEEPALIVE_MINUTES,
    MAX_PROGRAMMING_READ_INTERVAL,
    MIN_KEEPALIVE_MINUTES,
    MIN_PROGRAMMING_READ_INTERVAL,
    SUBENTRY_TYPE_PANEL,
    UNKNOWN_PANEL_POLICIES,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pyjfl import ConnectionInfo

    from . import JflConfigEntry, JflRuntimeData


def _hub_schema(host: str, port: int) -> vol.Schema:
    """Build the one question the user genuinely has to answer, plus where to bind."""
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
        return await self._async_host_step(user_input, step_id="user")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the listening address or port of an existing entry."""
        entry = self._get_reconfigure_entry()
        return await self._async_host_step(
            user_input,
            step_id="reconfigure",
            host=entry.data.get(CONF_HOST, DEFAULT_HOST),
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            reconfigure=entry,
        )

    async def _async_host_step(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        reconfigure: ConfigEntry | None = None,
    ) -> ConfigFlowResult:
        """Shared body of the user and reconfigure steps."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip() or DEFAULT_HOST
            port = int(user_input[CONF_PORT])

            if reconfigure is None:
                await self.async_set_unique_id(str(port))
                self._abort_if_unique_id_configured()
            elif self._port_belongs_to_another_entry(port, reconfigure):
                # The unique id **moves with the port**, because the port is what makes two
                # listeners incompatible. So the check is not "did the unique id change?" — it did,
                # that is the point — but "does another entry already own this port?".
                return self.async_abort(reason="wrong_listener")

            try:
                # Reconfiguring to the address it already has would be probed against our own
                # running listener and always fail, so only a genuine change is tested.
                if reconfigure is None or (host, port) != (
                    reconfigure.data.get(CONF_HOST),
                    reconfigure.data.get(CONF_PORT),
                ):
                    await self.hass.async_add_executor_job(
                        check_port_available, host, port
                    )
            except OSError as err:
                LOGGER.debug("cannot bind %s:%s: %s", host, port, err)
                errors["base"] = "port_in_use"
            else:
                data = {CONF_HOST: host, CONF_PORT: port}
                if reconfigure is not None:
                    return self.async_update_reload_and_abort(
                        reconfigure, data=data, unique_id=str(port)
                    )
                return self.async_create_entry(title=f"JFL Alarm ({port})", data=data)

        return self.async_show_form(
            step_id=step_id, data_schema=_hub_schema(host, port), errors=errors
        )

    def _port_belongs_to_another_entry(self, port: int, entry: ConfigEntry) -> bool:
        """Whether some *other* config entry is already the listener for *port*."""
        return any(
            other.unique_id == str(port) and other.entry_id != entry.entry_id
            for other in self._async_current_entries(include_ignore=False)
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: JflConfigEntry) -> OptionsFlow:
        """Return the hub options flow. **No constructor argument** — AGENTS.md §5."""
        return JflOptionsFlow()

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """One subentry type: a panel."""
        return {SUBENTRY_TYPE_PANEL: JflPanelSubentryFlow}


class JflOptionsFlow(OptionsFlow):
    """Hub-wide options: how often to poll, what to tell the panel, and how loud to be."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the hub options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_PROGRAMMING_READ_INTERVAL: int(
                        user_input[CONF_PROGRAMMING_READ_INTERVAL]
                    ),
                    CONF_KEEPALIVE_MINUTES: int(user_input[CONF_KEEPALIVE_MINUTES]),
                    CONF_LOG_RAW_FRAMES: bool(user_input[CONF_LOG_RAW_FRAMES]),
                    CONF_UNKNOWN_PANELS: str(user_input[CONF_UNKNOWN_PANELS]),
                }
            )

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PROGRAMMING_READ_INTERVAL,
                    default=options.get(
                        CONF_PROGRAMMING_READ_INTERVAL,
                        DEFAULT_PROGRAMMING_READ_INTERVAL,
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_PROGRAMMING_READ_INTERVAL,
                        max=MAX_PROGRAMMING_READ_INTERVAL,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_KEEPALIVE_MINUTES,
                    default=options.get(
                        CONF_KEEPALIVE_MINUTES, DEFAULT_KEEPALIVE_MINUTES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_KEEPALIVE_MINUTES,
                        max=MAX_KEEPALIVE_MINUTES,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_UNKNOWN_PANELS,
                    default=options.get(CONF_UNKNOWN_PANELS, DEFAULT_UNKNOWN_PANELS),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=UNKNOWN_PANEL_POLICIES,
                        translation_key=CONF_UNKNOWN_PANELS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_LOG_RAW_FRAMES,
                    default=options.get(CONF_LOG_RAW_FRAMES, DEFAULT_LOG_RAW_FRAMES),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class JflPanelSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure one panel.

    Adding a panel is normally not something anyone has to do: the listener creates the subentry
    when the panel dials in. This flow exists for the two cases where that does not happen — the
    panel is not powered yet, or the hub is set to hold unknown panels for approval.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer the panels that have already reported in, or take a serial by hand."""
        entry: JflConfigEntry = self._get_entry()
        errors: dict[str, str] = {}
        known = {
            subentry.unique_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_PANEL
        }
        pending = {
            serial: info
            for serial, info in _pending_panels(entry).items()
            if serial not in known
        }

        if user_input is not None:
            serial = str(user_input[CONF_SERIAL]).strip()
            if not serial:
                errors[CONF_SERIAL] = "invalid_serial"
            elif serial in known:
                return self.async_abort(reason="already_configured")
            else:
                info = pending.get(serial)
                title = f"{info.spec.name} {serial}" if info else f"JFL panel {serial}"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_SERIAL: serial,
                        CONF_READ_ONLY: bool(user_input[CONF_READ_ONLY]),
                        **_code_settings(user_input),
                    },
                    unique_id=serial,
                )

        serial_field: Any = TextSelector()
        if pending:
            # Everything about these panels is already known, so the user picks one rather than
            # copying a ten-character serial off a label.
            serial_field = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=serial, label=f"{info.spec.name} — {serial}"
                        )
                        for serial, info in sorted(pending.items())
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL): serial_field,
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

    The code is **optional and empty by default**: the panel's own keypad already has one, and
    demanding a second one from everybody would be a tax on the common case. It is a Home Assistant
    code and never reaches the panel — the commands this integration sends carry no password at all.

    Stripped, so that a stray space typed into the field does not produce a code nobody can enter.
    With no code set, "require it to arm" is meaningless and is stored as `False` rather than left
    to imply something.
    """
    code = str(user_input.get(CONF_CODE, DEFAULT_CODE) or "").strip()
    return {
        CONF_CODE: code,
        CONF_CODE_ARM_REQUIRED: bool(code)
        and bool(user_input.get(CONF_CODE_ARM_REQUIRED, DEFAULT_CODE_ARM_REQUIRED)),
    }


def _pending_panels(entry: JflConfigEntry) -> dict[str, ConnectionInfo]:
    """Panels that have dialled in without a subentry, if the entry is loaded.

    Returns nothing when the entry is not loaded: `runtime_data` only exists while it is, and a
    panel list is a convenience, never a requirement for adding one by hand. `getattr` rather than
    an attribute access for the same reason — Home Assistant does not set `runtime_data` until
    setup succeeds, so reading it directly raises on an entry that failed to load.
    """
    runtime: JflRuntimeData | None = getattr(entry, "runtime_data", None)
    if runtime is None:
        return {}
    return runtime.server.pending_panels

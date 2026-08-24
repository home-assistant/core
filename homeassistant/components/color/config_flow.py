"""Config flow for the Color helper.

Each color is its own config entry. The flow runs once at create-time; the
stored color itself is edited at runtime via the `color.set_color` action, so
the flow is intentionally minimal — pick a name, an initial color or color
temperature, and done.
"""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ICON, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_INITIAL_BRIGHTNESS,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DEFAULT_HEX,
    DEFAULT_KELVIN,
    DEFAULT_RGB,
    DOMAIN,
    MAX_KELVIN,
    MIN_KELVIN,
    MODE_CHROMATIC,
    MODE_WHITE,
)

_BRIGHTNESS_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=255, step=1, mode=selector.NumberSelectorMode.SLIDER
    )
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Optional(CONF_ICON): selector.IconSelector(),
        vol.Required(
            CONF_INITIAL_MODE, default=MODE_CHROMATIC
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[MODE_CHROMATIC, MODE_WHITE],
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_INITIAL_MODE,
            )
        ),
    }
)

CHROMATIC_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_INITIAL_COLOR, default=DEFAULT_RGB
        ): selector.ColorRGBSelector(),
        vol.Optional(CONF_INITIAL_BRIGHTNESS): _BRIGHTNESS_SELECTOR,
    }
)

WHITE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_INITIAL_KELVIN, default=DEFAULT_KELVIN
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_KELVIN,
                max=MAX_KELVIN,
                step=50,
                unit_of_measurement="K",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(CONF_INITIAL_BRIGHTNESS): _BRIGHTNESS_SELECTOR,
    }
)


def _coerce_color_input(raw: Any) -> str:
    """Coerce a ColorRGBSelector result ([r, g, b] list) to a hex string."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        try:
            r, g, b = (int(v) for v in raw)
        except TypeError, ValueError, OverflowError:
            return DEFAULT_HEX
        return f"#{r:02X}{g:02X}{b:02X}"
    return DEFAULT_HEX


class ColorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two-step flow: pick mode, then pick the corresponding initial value."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._stash: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

        self._stash.update(user_input)
        if user_input[CONF_INITIAL_MODE] == MODE_WHITE:
            return await self.async_step_white()
        return await self.async_step_chromatic()

    async def async_step_chromatic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial chromatic color step."""
        if user_input is None:
            return self.async_show_form(
                step_id="chromatic", data_schema=CHROMATIC_SCHEMA
            )
        initial_color = _coerce_color_input(user_input.get(CONF_INITIAL_COLOR))
        if initial_color == "#000000":
            return self.async_show_form(
                step_id="chromatic",
                data_schema=CHROMATIC_SCHEMA,
                errors={CONF_INITIAL_COLOR: "pure_black"},
            )
        return self._finalize(
            {
                **self._stash,
                CONF_INITIAL_COLOR: initial_color,
                CONF_INITIAL_BRIGHTNESS: user_input.get(CONF_INITIAL_BRIGHTNESS),
            }
        )

    async def async_step_white(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial color temperature step."""
        if user_input is None:
            return self.async_show_form(step_id="white", data_schema=WHITE_SCHEMA)
        return self._finalize(
            {
                **self._stash,
                CONF_INITIAL_KELVIN: int(user_input[CONF_INITIAL_KELVIN]),
                CONF_INITIAL_BRIGHTNESS: user_input.get(CONF_INITIAL_BRIGHTNESS),
            }
        )

    def _finalize(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry."""
        if data.get(CONF_INITIAL_BRIGHTNESS) is None:
            data.pop(CONF_INITIAL_BRIGHTNESS, None)
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return ColorOptionsFlow()


class ColorOptionsFlow(OptionsFlow):
    """Options flow letting the user change the icon after creation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Store None for "cleared" so it is distinct from "never set".
            return self.async_create_entry(data={CONF_ICON: user_input.get(CONF_ICON)})
        if CONF_ICON in self.config_entry.options:
            current_icon = self.config_entry.options[CONF_ICON]
        else:
            current_icon = self.config_entry.data.get(CONF_ICON)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ICON,
                    description={"suggested_value": current_icon},
                ): selector.IconSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

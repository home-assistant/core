"""Config flow for Volkszaehler integration."""

import logging
from types import MappingProxyType
from typing import Any, override

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import (
    VolkszaehlerApiConnectionError,
    VolkszaehlerNoDataAvailable,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UUID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN, SUBENTRY_TYPE_CHANNEL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_UUID): cv.string,
    }
)

STEP_SUBENTRY_DATA_SCHEMA = vol.Schema({vol.Required(CONF_UUID): cv.string})


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    api = Volkszaehler(
        session=async_get_clientsession(hass),
        uuid=data[CONF_UUID],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
    )
    await api.get_data()


async def _async_validate_input_errors(
    hass: HomeAssistant, data: dict[str, Any]
) -> str | None:
    """Validate input and return a config flow error key if validation fails."""
    try:
        await _validate_input(hass, data)
    except VolkszaehlerApiConnectionError:
        return "cannot_connect"
    except VolkszaehlerNoDataAvailable:
        return "no_data"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return None


def _is_uuid_configured(hass: HomeAssistant, uuid: str) -> bool:
    """Return if a Volkszaehler channel UUID is already configured."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == uuid:
            return True
        if any(
            subentry.unique_id == uuid
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_CHANNEL)
        ):
            return True
    return False


class VolkszaehlerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Volkszaehler."""

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_CHANNEL: VolkszaehlerSubentryFlow}

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Set the config entry up from yaml."""
        if error := await _async_validate_input_errors(self.hass, import_data):
            return self.async_abort(reason=error)

        uuid = import_data[CONF_UUID]
        if _is_uuid_configured(self.hass, uuid):
            return self.async_abort(reason="already_configured")

        channel_subentry = ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_CHANNEL,
            unique_id=uuid,
            title=import_data.get(CONF_NAME, uuid),
            data=MappingProxyType({CONF_UUID: uuid}),
        )

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data.get(CONF_HOST) == import_data[CONF_HOST]
                and entry.data.get(CONF_PORT, DEFAULT_PORT) == import_data[CONF_PORT]
            ):
                self.hass.config_entries.async_add_subentry(entry, channel_subentry)
                return self.async_abort(reason="subentry_added")

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data={
                CONF_HOST: import_data[CONF_HOST],
                CONF_PORT: import_data[CONF_PORT],
            },
            subentries=[channel_subentry.as_dict()],
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )
            if error := await _async_validate_input_errors(self.hass, user_input):
                errors["base"] = error
            else:
                if _is_uuid_configured(self.hass, user_input[CONF_UUID]):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    subentries=[
                        {
                            "subentry_type": SUBENTRY_TYPE_CHANNEL,
                            "title": user_input[CONF_UUID],
                            "data": {CONF_UUID: user_input[CONF_UUID]},
                            "unique_id": user_input[CONF_UUID],
                        }
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            )
            if user_input
            else STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class VolkszaehlerSubentryFlow(ConfigSubentryFlow):
    """Handle Volkszaehler channel subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a Volkszaehler channel subentry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if _is_uuid_configured(self.hass, user_input[CONF_UUID]):
                return self.async_abort(reason="already_configured")

            entry = self._get_entry()
            if error := await _async_validate_input_errors(
                self.hass,
                {
                    CONF_HOST: entry.data[CONF_HOST],
                    CONF_PORT: entry.data[CONF_PORT],
                    CONF_UUID: user_input[CONF_UUID],
                },
            ):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_UUID],
                    data={CONF_UUID: user_input[CONF_UUID]},
                    unique_id=user_input[CONF_UUID],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SUBENTRY_DATA_SCHEMA, user_input
            )
            if user_input
            else STEP_SUBENTRY_DATA_SCHEMA,
            errors=errors,
        )

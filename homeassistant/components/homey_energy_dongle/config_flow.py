"""Config flow for the Homey Energy Dongle integration."""

import asyncio
from collections.abc import Mapping
from contextlib import aclosing
import logging
from typing import TYPE_CHECKING, Any, override

from homey_energy_dongle_ws import (
    DSMR_VERSIONS,
    ConnectionLimitError,
    HomeyWebSocketError,
    LocalApiDisabledError,
    TelegramParseError,
    detect_dsmr_version,
    parse_telegram,
    service_instance_display_name,
)
from homey_energy_dongle_ws.parser import TELEGRAM_SPECIFICATIONS
import probatio

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DSMR_VERSION,
    CONF_WS_PATH,
    DEFAULT_PORT,
    DEFAULT_WS_PATH,
    DOMAIN,
)
from .coordinator import TELEGRAM_TIMEOUT, create_client

_LOGGER = logging.getLogger(__name__)

# Values such as "2.2" are not valid translation keys.
_DSMR_VERSION_LABELS = {
    "5": "DSMR 5",
    "5B": "DSMR 5B (Belgium, Fluvius)",
    "5L": "DSMR 5L (Luxembourg)",
    "5S": "DSMR 5S (Sweden)",
    "Q3D": "Q3D (Austria)",
    "5EONHU": "DSMR 5 (E.ON Hungary)",
    "4": "DSMR 4",
    "2.2": "DSMR 2.2",
}
_VERSION_FIELD = {
    probatio.Required(CONF_DSMR_VERSION): SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=code, label=_DSMR_VERSION_LABELS[code])
                for code in DSMR_VERSIONS
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )
}
STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})
STEP_VERSION_SCHEMA = probatio.Schema(_VERSION_FIELD)
STEP_RECONFIGURE_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_HOST): str, **_VERSION_FIELD}
)


class HomeyEnergyDongleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homey Energy Dongle.

    An entry is identified by the dongle ID it advertises over mDNS. Dongles
    added by address have no unique ID until they are discovered. The meters
    are identified per telegram by the sensors, not by the entry.
    """

    VERSION = 1

    _discovered: dict[str, str | int] | None = None
    _title = "Homey Energy Dongle"
    _telegram: str | None = None
    _detected_version: str | None = None

    async def _async_read_telegram(self, data: Mapping[str, Any]) -> str | None:
        """Store one raw telegram. Return an error key on failure."""
        self._telegram = None
        self._detected_version = None
        try:
            async with (
                asyncio.timeout(TELEGRAM_TIMEOUT),
                create_client(data) as client,
                aclosing(client.stream_telegrams()) as telegrams,
            ):
                self._telegram = await anext(telegrams)
        except LocalApiDisabledError:
            return "local_api_disabled"
        except ConnectionLimitError:
            return "too_many_connections"
        except TimeoutError, HomeyWebSocketError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        self._detected_version = detect_dsmr_version(self._telegram)
        return None

    def _version_error(self, version: str) -> str | None:
        """Return an error key when the cached telegram doesn't parse with ``version``."""
        if TYPE_CHECKING:
            assert self._telegram is not None
        try:
            parse_telegram(
                self._telegram, telegram_specification=TELEGRAM_SPECIFICATIONS[version]
            )
        except TelegramParseError:
            return "invalid_dsmr_version"
        return None

    async def _async_probe(self, data: Mapping[str, Any]) -> str | None:
        """Read one telegram and keep the detected profile if it parses."""
        if error := await self._async_read_telegram(data):
            return error
        if self._detected_version is not None and self._version_error(
            self._detected_version
        ):
            # The profile matched, but this frame does not parse. Ask instead.
            self._detected_version = None
        return None

    async def _async_create_entry(self, version: str) -> ConfigFlowResult:
        """Create the entry from the discovered address and meter profile."""
        if TYPE_CHECKING:
            assert self._discovered is not None
        self._async_abort_entries_match({CONF_HOST: self._discovered[CONF_HOST]})
        return self.async_create_entry(
            title=self._title,
            data={**self._discovered, CONF_DSMR_VERSION: version},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup with the IP address from the Homey app."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            self._discovered = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_WS_PATH: DEFAULT_WS_PATH,
            }
            if (error := await self._async_probe(self._discovered)) is None:
                if self._detected_version is not None:
                    return await self._async_create_entry(self._detected_version)
                return await self.async_step_dsmr_version()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_dsmr_version(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the meter profile when the telegram did not identify it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            version = user_input[CONF_DSMR_VERSION]
            if (error := self._version_error(version)) is None:
                return await self._async_create_entry(version)
            errors["base"] = error

        return self.async_show_form(
            step_id="dsmr_version",
            data_schema=self.add_suggested_values_to_schema(
                STEP_VERSION_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of an Energy Dongle."""
        self._discovered = {
            CONF_HOST: discovery_info.host,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
            CONF_WS_PATH: discovery_info.properties.get("p") or DEFAULT_WS_PATH,
        }
        # The dongle advertises itself as "Homey Energy Dongle <id>".
        dongle_id = service_instance_display_name(discovery_info.name).rpartition(" ")[
            2
        ]
        await self.async_set_unique_id(dongle_id)
        self._abort_if_unique_id_configured(updates=self._discovered)
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] == discovery_info.host:
                # Added by address, so it learns its ID now to follow the dongle.
                if entry.unique_id is None:
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=dongle_id
                    )
                return self.async_abort(reason="already_configured")
        self._title = f"Homey Energy Dongle ({dongle_id})"
        self.context["title_placeholders"] = {"name": self._title}
        # Detect the meter profile now; connection errors are shown on confirm.
        await self._async_probe(self._discovered)
        if self._telegram is None:
            return await self.async_step_zeroconf_meter()
        if self._detected_version is None:
            return await self.async_step_dsmr_version()
        if not onboarding.async_is_onboarded(self.hass):
            return await self._async_create_entry(self._detected_version)
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered dongle whose meter profile was detected."""
        if TYPE_CHECKING:
            assert self._detected_version is not None

        if user_input is not None:
            return await self._async_create_entry(self._detected_version)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._title,
                "version": _DSMR_VERSION_LABELS[self._detected_version],
            },
        )

    async def async_step_zeroconf_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered dongle that could not be read on discovery."""
        if TYPE_CHECKING:
            assert self._discovered is not None

        errors: dict[str, str] = {}
        if user_input is not None:
            if (error := await self._async_probe(self._discovered)) is not None:
                errors["base"] = error
            elif self._detected_version is not None:
                return await self._async_create_entry(self._detected_version)
            else:
                return await self.async_step_dsmr_version()

        return self.async_show_form(
            step_id="zeroconf_meter",
            description_placeholders={"name": self._title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address or DSMR version of a configured dongle."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            data = {**entry.data, **user_input}
            error = await self._async_read_telegram(data) or self._version_error(
                data[CONF_DSMR_VERSION]
            )
            if error is None:
                # Only discovery tells which dongle answers on a new address.
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=(
                        entry.unique_id
                        if user_input[CONF_HOST] == entry.data[CONF_HOST]
                        else None
                    ),
                    data_updates=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

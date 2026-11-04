"""Config flow for the Homey Energy Dongle integration."""

import asyncio
from collections.abc import Mapping
from contextlib import aclosing
import logging
from typing import TYPE_CHECKING, Any, Self, override

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
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
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
# dsmr-parser names the meter's identifier differently per profile.
_IDENTIFIER_FIELDS = (
    "EQUIPMENT_IDENTIFIER",
    "BELGIUM_EQUIPMENT_IDENTIFIER",
    "LUXEMBOURG_EQUIPMENT_IDENTIFIER",
    "Q3D_EQUIPMENT_IDENTIFIER",
)
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
    """Handle a config flow for Homey Energy Dongle."""

    VERSION = 1

    _discovered: dict[str, str | int] | None = None
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

    async def _async_identify(
        self, data: Mapping[str, Any], version: str
    ) -> str | None:
        """Parse the cached telegram with ``version`` and set the unique id.

        Swedish and Hungarian meters don't send an identifier, so those are
        matched on host.
        """
        if TYPE_CHECKING:
            assert self._telegram is not None
        try:
            telegram = parse_telegram(
                self._telegram,
                telegram_specification=TELEGRAM_SPECIFICATIONS[version],
            )
        except TelegramParseError:
            return "invalid_dsmr_version"
        identifier = next(
            (
                obj
                for field in _IDENTIFIER_FIELDS
                if (obj := getattr(telegram, field, None)) is not None
            ),
            None,
        )
        await self.async_set_unique_id(
            None if identifier is None else str(identifier.value)
        )
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch()
        elif self.unique_id:
            self._abort_if_unique_id_configured(updates=dict(data))
        if not self.unique_id:
            self._async_abort_entries_match({CONF_HOST: data[CONF_HOST]})
        return None

    async def _async_probe(self, data: Mapping[str, Any]) -> str | None:
        """Read one telegram and identify the meter when its profile is known."""
        if error := await self._async_read_telegram(data):
            return error
        if self._detected_version is not None and await self._async_identify(
            data, self._detected_version
        ):
            # The profile matched, but this frame does not parse. Ask instead.
            self._detected_version = None
        return None

    def _async_create_entry(self, title: str, version: str) -> ConfigFlowResult:
        """Create the entry from the discovered address and meter profile."""
        if TYPE_CHECKING:
            assert self._discovered is not None
        return self.async_create_entry(
            title=title,
            data={**self._discovered, CONF_DSMR_VERSION: version},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup with the IP address from the Homey app."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._discovered = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: DEFAULT_PORT,
                CONF_WS_PATH: DEFAULT_WS_PATH,
            }
            if (error := await self._async_probe(self._discovered)) is None:
                if self._detected_version is not None:
                    return self._async_create_entry(
                        "Homey Energy Dongle", self._detected_version
                    )
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
        if TYPE_CHECKING:
            assert self._discovered is not None

        errors: dict[str, str] = {}
        if user_input is not None:
            version = user_input[CONF_DSMR_VERSION]
            if (error := await self._async_identify(self._discovered, version)) is None:
                return self._async_create_entry("Homey Energy Dongle", version)
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
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})
        self._discovered = {
            CONF_HOST: discovery_info.host,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
            CONF_WS_PATH: discovery_info.properties.get("p") or DEFAULT_WS_PATH,
        }
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")
        # The dongle advertises itself as "Homey Energy Dongle <id>".
        dongle_id = service_instance_display_name(discovery_info.name).rpartition(" ")[
            2
        ]
        name = f"Homey Energy Dongle ({dongle_id})"
        self.context["title_placeholders"] = {"name": name}
        # Lets the user ignore a dongle that can't be read yet. Reading a
        # telegram replaces it with the meter's identifier.
        await self.async_set_unique_id(f"dongle_{dongle_id}")
        self._abort_if_unique_id_configured()
        # The meter's identifier is only in telegrams, so read one to recognize a
        # configured dongle on a new address. Connection errors are shown when
        # the user confirms.
        await self._async_probe(self._discovered)
        if self._telegram is None:
            return await self.async_step_zeroconf_meter()
        if self._detected_version is None:
            return await self.async_step_dsmr_version()
        if not onboarding.async_is_onboarded(self.hass):
            return self._async_create_entry(name, self._detected_version)
        return await self.async_step_zeroconf_confirm()

    @override
    def is_matching(self, other_flow: Self) -> bool:
        """Return True if the other flow discovered the same dongle."""
        if TYPE_CHECKING:
            assert self._discovered is not None
        return (
            other_flow._discovered is not None
            and other_flow._discovered[CONF_HOST] == self._discovered[CONF_HOST]
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered dongle whose meter profile was detected."""
        if TYPE_CHECKING:
            assert self._discovered is not None
            assert self._detected_version is not None

        name = self.context["title_placeholders"]["name"]
        if user_input is not None:
            return self._async_create_entry(name, self._detected_version)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": name,
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
        name = self.context["title_placeholders"]["name"]
        if user_input is not None:
            if (error := await self._async_probe(self._discovered)) is not None:
                errors["base"] = error
            elif self._detected_version is not None:
                return self._async_create_entry(name, self._detected_version)
            else:
                return await self.async_step_dsmr_version()

        return self.async_show_form(
            step_id="zeroconf_meter",
            description_placeholders={"name": name},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address or DSMR version of a configured dongle."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            error = await self._async_read_telegram(data) or await self._async_identify(
                data, data[CONF_DSMR_VERSION]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

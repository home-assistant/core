"""Config flow for Fronius integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from pyfronius import Fronius, FroniusError
import voluptuous as vol

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, FroniusConfigEntryData

_LOGGER: Final = logging.getLogger(__name__)

DHCP_REQUEST_DELAY: Final = 60


def create_title(info: FroniusConfigEntryData) -> str:
    """Return the title of the config flow."""
    return (
        f"SolarNet {'Datalogger' if info['is_logger'] else 'Inverter'}"
        f" at {info['host']}"
    )


async def validate_host(
    hass: HomeAssistant, host: str
) -> tuple[str, FroniusConfigEntryData]:
    """Validate the user input allows us to connect."""
    fronius = Fronius(async_get_clientsession(hass), host)

    try:
        datalogger_info: dict[str, Any]
        datalogger_info = await fronius.current_logger_info()
    except FroniusError as err:
        _LOGGER.debug(err)
    else:
        logger_uid: str = datalogger_info["unique_identifier"]["value"]
        return logger_uid, FroniusConfigEntryData(
            host=host,
            is_logger=True,
        )
    # Gen24 devices don't provide GetLoggerInfo
    try:
        inverter_info = await fronius.inverter_info()
        first_inverter = next(inverter for inverter in inverter_info["inverters"])
    except FroniusError as err:
        _LOGGER.debug(err)
        raise CannotConnect from err
    except StopIteration as err:
        raise CannotConnect("No supported Fronius SolarNet device found.") from err
    first_inverter_uid: str = first_inverter["unique_id"]["value"]
    return first_inverter_uid, FroniusConfigEntryData(
        host=host,
        is_logger=False,
    )


class FroniusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fronius."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.info: FroniusConfigEntryData
        self._entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                unique_id, info = await validate_host(self.hass, user_input[CONF_HOST])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates=dict(info))

                return self.async_create_entry(title=create_title(info), data=info)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the DHCP client."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST].removeprefix("http://").rstrip("/").lower() in (
                discovery_info.ip,
                discovery_info.hostname,
            ):
                return self.async_abort(reason="already_configured")
        # Symo Datalogger devices need up to 1 minute at boot from DHCP request
        # to respond to API requests (connection refused until then)
        await asyncio.sleep(DHCP_REQUEST_DELAY)
        try:
            unique_id, self.info = await validate_host(self.hass, discovery_info.ip)
        except CannotConnect:
            return self.async_abort(reason="invalid_host")

        await self.async_set_unique_id(unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates=dict(self.info))

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to confirm."""
        title = create_title(self.info)
        if user_input is not None:
            return self.async_create_entry(title=title, data=self.info)

        self._set_confirm_only()
        self.context.update({"title_placeholders": {"device": title}})
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "device": title,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        errors = {}

        if user_input is not None:
            try:
                unique_id, info = await validate_host(self.hass, user_input[CONF_HOST])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                existing_entry = await self.async_set_unique_id(
                    unique_id, raise_on_progress=False
                )
                assert self._entry is not None
                if existing_entry and existing_entry.entry_id != self._entry.entry_id:
                    self._abort_if_unique_id_configured()

                return self.async_update_reload_and_abort(
                    self._entry,
                    data=info,
                    reason="reconfigure_successful",
                )

        if self._entry is None:
            self._entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            assert self._entry is not None
        host = self._entry.data[CONF_HOST]
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
            description_placeholders={"device": self._entry.title},
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

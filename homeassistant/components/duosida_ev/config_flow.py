"""Config flow for the Duosida EV Charger integration."""

from ipaddress import ip_address
import logging
from typing import Any, override

from duosida_ev import (
    ChargerInfo,
    DiscoveryError,
    DuosidaError,
    discover_chargers,
    identify_charger,
)
import probatio

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MANUAL_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


class DuosidaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duosida EV Charger.

    The charger accepts a single session, so the flow never contacts a charger
    that is already set up. Chargers are compared by IP address.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, ChargerInfo] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user search the network or enter an address."""
        return self.async_show_menu(step_id="user", menu_options=["search", "manual"])

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Find chargers on the network and let the user pick one."""
        if user_input is not None:
            host = user_input[CONF_DEVICE]
            return await self._async_create_charger_entry(host, self._discovered[host])

        configured = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        targets = [
            str(address)
            for address in await async_get_ipv4_broadcast_addresses(self.hass)
        ]
        try:
            found = await discover_chargers(targets=targets, identify=False)
        except DiscoveryError:
            found = []
        for charger in found:
            if charger.host in configured:
                continue
            try:
                self._discovered[charger.host] = await identify_charger(charger.host)
            except DuosidaError:
                _LOGGER.debug("Cannot identify the charger at %s", charger.host)

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="search",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=host,
                                    label=f"{info.model or 'Duosida'} ({host})",
                                )
                                for host, info in self._discovered.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a charger from its IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = str(ip_address(user_input[CONF_HOST]))
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                try:
                    info = await identify_charger(host)
                except DuosidaError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return await self._async_create_charger_entry(host, info)

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(MANUAL_SCHEMA, user_input),
            errors=errors,
        )

    async def _async_create_charger_entry(
        self, host: str, info: ChargerInfo
    ) -> ConfigFlowResult:
        """Create the entry, or update the address of a configured charger."""
        await self.async_set_unique_id(info.device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return self.async_create_entry(
            title="Duosida EV Charger", data={CONF_HOST: host}
        )

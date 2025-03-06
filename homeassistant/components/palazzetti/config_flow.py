"""Config flow for Palazzetti."""

from typing import Any

from pypalazzetti.client import PalazzettiClient
from pypalazzetti.exceptions import CommunicationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN, LOGGER


class PalazzettiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Palazzetti config flow."""

    _discovered_device: PalazzettiClient

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            client = PalazzettiClient(hostname=host)
            try:
                await client.connect()
            except CommunicationError:
                LOGGER.exception("Communication error")
                errors["base"] = "cannot_connect"
            else:
                formatted_mac = dr.format_mac(client.mac)

                # Assign a unique ID to the flow
                await self.async_set_unique_id(formatted_mac)

                # Abort the flow if a config entry with the same unique ID exists
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=client.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""

        LOGGER.debug(
            "DHCP discovery detected Palazzetti: %s", discovery_info.macaddress
        )

        await self.async_set_unique_id(dr.format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured()
        self._discovered_device = PalazzettiClient(hostname=discovery_info.ip)
        try:
            await self._discovered_device.connect()
        except CommunicationError:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_device.name,
                data={CONF_HOST: self._discovered_device.host},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._discovered_device.name,
                "host": self._discovered_device.host,
            },
        )

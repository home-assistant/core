"""Config flow for Qube Heat Pump integration."""

from typing import Any, override

import probatio
from python_qube_heatpump import QubeClient, async_get_device_info, parse_device_info

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN, MDNS_LOOKUP_TIMEOUT

HOST_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})


async def _async_validate_device(host: str) -> str | None:
    """Connect and verify the device is a Qube; return an error key on failure."""
    client = QubeClient(host, DEFAULT_PORT)
    try:
        if not await client.connect():
            return "cannot_connect"
        if await client.async_get_software_version() is None:
            return "not_qube_device"
    except OSError:
        return "cannot_connect"
    finally:
        await client.close()
    return None


class QubeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qube Heat Pump."""

    VERSION = 1

    _host: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            self._async_abort_entries_match({CONF_HOST: host})

            if error := await _async_validate_device(host):
                errors["base"] = error
            else:
                # The controller's mDNS record carries a stable uuid; without
                # mDNS (e.g. across VLANs) the entry is created without one
                aiozc = await zeroconf.async_get_async_instance(self.hass)
                if device := await async_get_device_info(
                    host, aiozc, timeout=MDNS_LOOKUP_TIMEOUT
                ):
                    await self.async_set_unique_id(device.uuid)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self._async_create_qube_entry(host)

        return self.async_show_form(
            step_id="user", data_schema=HOST_SCHEMA, errors=errors
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a Qube discovered through its mDNS advertisement."""
        if (device := parse_device_info(discovery_info.properties)) is None:
            return self.async_abort(reason="not_qube_device")

        host = discovery_info.host
        await self.async_set_unique_id(device.uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Entries created without mDNS have no unique id yet; adopt the one
        # whose host is this controller (any advertised IP or the mDNS hostname)
        controller_hosts = {str(ip) for ip in discovery_info.ip_addresses}
        controller_hosts.add(discovery_info.hostname.lower().rstrip("."))
        for entry in self._async_current_entries(include_ignore=False):
            configured_host = entry.data[CONF_HOST].lower().rstrip(".")
            if entry.unique_id is None and configured_host in controller_hosts:
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=device.uuid
                )
                return self.async_abort(reason="already_configured")

        self._host = host
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setting up a discovered Qube."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if error := await _async_validate_device(self._host):
                errors["base"] = error
            else:
                return self._async_create_qube_entry(self._host)

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host": self._host},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the host of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if error := await _async_validate_device(host):
                errors["base"] = error
            else:
                # Refuse a different controller when both uuids are known;
                # without mDNS the Modbus check above is all we can verify
                if entry.unique_id is not None:
                    aiozc = await zeroconf.async_get_async_instance(self.hass)
                    if device := await async_get_device_info(
                        host, aiozc, timeout=MDNS_LOOKUP_TIMEOUT
                    ):
                        await self.async_set_unique_id(device.uuid)
                        self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(HOST_SCHEMA, entry.data),
            errors=errors,
        )

    def _async_create_qube_entry(self, host: str) -> ConfigFlowResult:
        """Create the config entry for a verified Qube."""
        return self.async_create_entry(
            title="Qube heat pump",
            data={
                CONF_HOST: host,
                CONF_PORT: DEFAULT_PORT,
            },
        )

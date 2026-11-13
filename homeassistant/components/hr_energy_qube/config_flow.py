"""Config flow for Qube Heat Pump integration."""

from typing import Any, override

from modbus_connection import ModbusTcpParams
import probatio
from python_qube_heatpump import QubeClient, async_get_device_info, parse_device_info

from homeassistant.components import zeroconf
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN, MDNS_LOOKUP_TIMEOUT, UNIT_ID

HOST_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


async def _async_validate_device(hass: HomeAssistant, host: str) -> str | None:
    """Verify the device is a Qube; return an error key on failure."""
    try:
        async with async_get_temporary_unit(
            hass, ModbusTcpParams(host=host, port=DEFAULT_PORT), UNIT_ID
        ) as unit:
            client = QubeClient(host, DEFAULT_PORT, UNIT_ID, unit=unit)
            if await client.async_verify_device():
                return None
            # A failed request drops the link; an error reply leaves it up
            return "not_qube_device" if client.is_connected else "cannot_connect"
    except HomeAssistantError:
        # The device is already in use over different link settings
        return "cannot_connect"


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

            if error := await _async_validate_device(self.hass, host):
                errors["base"] = error
            else:
                # The controller's mDNS record carries a stable uuid; without
                # mDNS (e.g. across VLANs) the entry is created without one
                aiozc = await zeroconf.async_get_async_instance(self.hass)
                device = await async_get_device_info(
                    host, aiozc, timeout=MDNS_LOOKUP_TIMEOUT
                )
                if device and not await self._async_uuid_of_other_qube(
                    device.uuid, host
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
        if await self._async_uuid_of_other_qube(device.uuid, host):
            return self.async_abort(reason="already_configured")
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
            if error := await _async_validate_device(self.hass, self._host):
                errors["base"] = error
            else:
                return self._async_create_qube_entry(self._host)

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

            self._async_abort_entries_match({CONF_HOST: host})

            if error := await _async_validate_device(self.hass, host):
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

    async def _async_uuid_of_other_qube(self, uuid: str, host: str) -> bool:
        """Return True when the entry keyed on ``uuid`` is another Qube.

        Every Qube announces the same mDNS name and two can report the same
        uuid. A uuid seen at a new address only means the heat pump moved when
        no other entry uses that address and the old one no longer answers.
        """
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, uuid)
        if (
            entry is None
            or entry.source == SOURCE_IGNORE
            or entry.data[CONF_HOST] == host
        ):
            return False
        if any(
            other.data[CONF_HOST] == host
            for other in self._async_current_entries(include_ignore=False)
        ):
            return True
        return await _async_validate_device(self.hass, entry.data[CONF_HOST]) is None

    def _async_create_qube_entry(self, host: str) -> ConfigFlowResult:
        """Create the config entry for a verified Qube."""
        return self.async_create_entry(
            title="Qube heat pump",
            data={
                CONF_HOST: host,
                CONF_PORT: DEFAULT_PORT,
            },
        )

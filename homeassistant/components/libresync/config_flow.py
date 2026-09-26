"""Config flow for the LibreSync integration."""

from typing import Any, override
from urllib.parse import urlparse

from aiolibresync import (
    DiscoveredDevice,
    async_probe,
    async_probe_control,
    async_read_serial,
)
import probatio

from homeassistant.config_entries import (
    DISCOVERY_SOURCES,
    SOURCE_IGNORE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import TextSelector
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import CONF_SERIAL, CONF_UDN, DEFAULT_NAME, DOMAIN

STEP_USER_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


class LibreSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for LibreSync.

    A hub is identified by its factory serial when it has a valid one, and by
    its UPnP UDN otherwise. The serial does not depend on the UPnP daemon, which
    can stop on an otherwise healthy hub; the UDN is what discovery sees
    without connecting. Both are kept in the entry data, and every path checks
    both, so a hub is recognised whichever one it sees.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered: DiscoveredDevice | None = None
        self._serial: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a hub added by address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            device = await async_probe(host)
            if device is None:
                errors["base"] = "cannot_connect"
            else:
                # Before the serial is read, which opens a second session next
                # to the running client's.
                self._async_abort_if_known(host, udn=device.udn)
                serial = await async_read_serial(host)
                if serial is None and device.udn is None:
                    errors["base"] = "no_identity"
                else:
                    self._async_abort_if_known(host, serial=serial, udn=device.udn)
                    await self.async_set_unique_id(
                        serial or device.udn, raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured()
                    await self._async_remove_ignored(device.udn)
                    return self.async_create_entry(
                        title=device.name or DEFAULT_NAME,
                        data=_entry_data(host, serial, device.udn),
                    )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a hub found by SSDP."""
        udn = discovery_info.upnp.get(ATTR_UPNP_UDN)
        host = urlparse(discovery_info.ssdp_location or "").hostname
        if not udn or not host:
            return self.async_abort(reason="cannot_connect")

        # A known hub is recognised by its UDN before anything is sent to it.
        self._async_abort_if_known(host, udn=udn)
        # The UDN is the unique ID until the entry is created, so an ignored
        # hub, and a second discovery of one being set up, stop here too.
        await self.async_set_unique_id(udn)
        self._abort_if_unique_id_configured()

        if not await async_probe_control(host):
            return self.async_abort(reason="cannot_connect")
        self._serial = await async_read_serial(host)
        self._async_abort_if_known(host, serial=self._serial, udn=udn)

        self._discovered = DiscoveredDevice(
            host=host, udn=udn, name=discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME)
        )
        self.context["title_placeholders"] = {
            "name": self._discovered.name or DEFAULT_NAME
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered hub."""
        assert self._discovered is not None
        name = self._discovered.name or DEFAULT_NAME
        if user_input is not None:
            host, udn = self._discovered.host, self._discovered.udn
            # The hub may have been added by address in the meantime.
            self._async_abort_if_known(host, serial=self._serial, udn=udn)
            await self.async_set_unique_id(self._serial or udn, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name, data=_entry_data(host, self._serial, udn)
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": name}
        )

    async def _async_remove_ignored(self, udn: str | None) -> None:
        """Remove a discovery the user ignored under the UDN of this hub.

        Home Assistant replaces an ignored entry that has the new entry's unique
        ID, but discovery ignores a hub under its UDN, and an entry created here
        is keyed on the serial when there is one.
        """
        for entry in self._async_current_entries(include_ignore=True):
            if udn and entry.source == SOURCE_IGNORE and entry.unique_id == udn:
                await self.hass.config_entries.async_remove(entry.entry_id)

    def _async_abort_if_known(
        self, host: str, *, serial: str | None = None, udn: str | None = None
    ) -> None:
        """Abort if an entry already carries either identifier.

        The entry follows the hub to its new address, and learns an identifier
        it did not have yet. It is reloaded as `_abort_if_unique_id_configured`
        would: when its data changed, or when a discovery finds a hub whose
        setup is waiting to retry.
        """
        seen = {value for value in (serial, udn) if value}
        for entry in self._async_current_entries(include_ignore=False):
            known = {
                entry.unique_id,
                entry.data.get(CONF_SERIAL),
                entry.data.get(CONF_UDN),
            }
            if not seen & known:
                continue
            changed = self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, **_entry_data(host, serial, udn)}
            )
            if (
                changed
                and entry.state
                in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)
            ) or (
                self.source in DISCOVERY_SOURCES
                and entry.state is ConfigEntryState.SETUP_RETRY
            ):
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            raise AbortFlow("already_configured")


def _entry_data(host: str, serial: str | None, udn: str | None) -> dict[str, Any]:
    """Return entry data holding every identifier that is known."""
    data: dict[str, Any] = {CONF_HOST: host}
    if serial:
        data[CONF_SERIAL] = serial
    if udn:
        data[CONF_UDN] = udn
    return data

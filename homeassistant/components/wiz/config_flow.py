"""Config flow for WiZ Platform."""

import logging
from typing import Any, override

import probatio
from pywizlight import BulbType, wizlight
from pywizlight.discovery import DiscoveredBulb
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

from homeassistant.components import onboarding
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.util.network import is_ip_address

from .const import (
    CONF_SIGNING_KEY,
    DEFAULT_NAME,
    DISCOVER_SCAN_TIMEOUT,
    DOMAIN,
    WIZ_CONNECT_EXCEPTIONS,
)
from .discovery import async_discover_devices
from .utils import _short_mac, name_from_bulb_type_and_mac

_LOGGER = logging.getLogger(__name__)

SIGNING_KEY_LENGTH = 16
SIGNING_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _normalize_signing_key(signing_key: str) -> str | None:
    """Return the signing key in lowercase hex, or None if it is not valid."""
    signing_key = signing_key.strip().lower()
    try:
        key = bytes.fromhex(signing_key)
    except ValueError:
        return None
    return signing_key if len(key) == SIGNING_KEY_LENGTH else None


def _validate_signing_key(signing_key: str) -> tuple[str | None, dict[str, str]]:
    """Return the normalized signing key, or the form errors."""
    if not signing_key.strip():
        return None, {}
    if (normalized := _normalize_signing_key(signing_key)) is None:
        return None, {CONF_SIGNING_KEY: "invalid_signing_key"}
    return normalized, {}


def _entry_data(host: str, signing_key: str | None) -> dict[str, str]:
    """Return config entry data, including the signing key only when set."""
    data = {CONF_HOST: host}
    if signing_key:
        data[CONF_SIGNING_KEY] = signing_key
    return data


class WizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ."""

    VERSION = 1

    _discovered_device: DiscoveredBulb
    _name: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, DiscoveredBulb] = {}
        self._signing_key: str | None = None

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        self._discovered_device = DiscoveredBulb(
            discovery_info.ip, discovery_info.macaddress
        )
        return await self._async_handle_discovery()

    @override
    async def async_step_integration_discovery(
        self, discovery_info: dict[str, str]
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        self._discovered_device = DiscoveredBulb(
            discovery_info["ip_address"], discovery_info["mac_address"]
        )
        return await self._async_handle_discovery()

    async def _async_handle_discovery(self) -> ConfigFlowResult:
        """Handle any discovery."""
        device = self._discovered_device
        _LOGGER.debug("Discovered device: %s", device)
        ip_address = device.ip_address
        mac = device.mac_address
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: ip_address})
        await self._async_connect_discovered_or_abort()
        return await self.async_step_discovery_confirm()

    async def _async_connect_discovered_or_abort(self) -> None:
        """Connect to the device and verify its responding."""
        device = self._discovered_device
        bulb = wizlight(device.ip_address)
        try:
            bulbtype = await bulb.get_bulbtype()
        except WIZ_CONNECT_EXCEPTIONS as ex:
            _LOGGER.debug(
                "Failed to connect to %s during discovery: %s",
                device.ip_address,
                ex,
                exc_info=True,
            )
            raise AbortFlow("cannot_connect") from ex
        finally:
            await bulb.async_close()
        self._name = name_from_bulb_type_and_mac(bulbtype, device.mac_address)

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        ip_address = self._discovered_device.ip_address
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            # Make sure the device is still there and
            # update the name if the firmware has auto
            # updated since discovery
            await self._async_connect_discovered_or_abort()
            return self.async_create_entry(
                title=self._name,
                data={CONF_HOST: ip_address},
            )

        placeholders = {"name": self._name, "host": ip_address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            device = self._discovered_devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(device.mac_address, raise_on_progress=False)
            bulb = wizlight(device.ip_address, signing_key=self._signing_key)
            try:
                bulbtype = await bulb.get_bulbtype()
            except WIZ_CONNECT_EXCEPTIONS:
                return self.async_abort(reason="cannot_connect")
            finally:
                await bulb.async_close()

            return self.async_create_entry(
                title=name_from_bulb_type_and_mac(bulbtype, device.mac_address),
                data=_entry_data(device.ip_address, self._signing_key),
            )

        current_unique_ids = self._async_current_ids(include_ignore=False)
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = await async_discover_devices(
            self.hass, DISCOVER_SCAN_TIMEOUT
        )
        self._discovered_devices = {
            device.mac_address: device for device in discovered_devices
        }
        devices_name = {
            mac: f"{DEFAULT_NAME} {_short_mac(mac)} ({device.ip_address})"
            for mac, device in self._discovered_devices.items()
            if mac not in current_unique_ids and device.ip_address not in current_hosts
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_DEVICE): probatio.In(devices_name)}
            ),
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        bulb_info: tuple[BulbType, str] | None = None
        if user_input is not None:
            signing_key, errors = _validate_signing_key(
                user_input.get(CONF_SIGNING_KEY, "")
            )
            if not errors:
                self._signing_key = signing_key
                if not (host := user_input[CONF_HOST]):
                    return await self.async_step_pick_device()
                bulb_info, errors = await self._async_validate_host(host)
            if bulb_info is not None:
                bulbtype, mac = bulb_info
                await self.async_set_unique_id(mac, raise_on_progress=False)
                data = _entry_data(host, signing_key)
                entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, mac
                )
                # A loaded entry reloads itself through its update listener
                self._abort_if_unique_id_configured(
                    updates=data,
                    reload_on_update=not (entry and entry.update_listeners),
                )
                name = name_from_bulb_type_and_mac(bulbtype, mac)
                return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_HOST, default=""): str,
                    probatio.Optional(
                        probatio.Secret(CONF_SIGNING_KEY)
                    ): SIGNING_KEY_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device IP address."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            bulb_info: tuple[BulbType, str] | None = None
            signing_key, errors = _validate_signing_key(
                user_input.get(CONF_SIGNING_KEY, "")
            )
            # Leaving the field blank keeps the current key
            signing_key = signing_key or reconfigure_entry.data.get(CONF_SIGNING_KEY)
            if not errors:
                bulb_info, errors = await self._async_validate_host(
                    user_input[CONF_HOST], signing_key
                )
            if bulb_info is not None:
                await self.async_set_unique_id(bulb_info[1])
                self._abort_if_unique_id_mismatch()
                data = _entry_data(user_input[CONF_HOST], signing_key)
                # The update listener is only registered after a successful setup
                if reconfigure_entry.update_listeners:
                    return self.async_update_and_abort(reconfigure_entry, data=data)
                return self.async_update_reload_and_abort(reconfigure_entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): str,
                        probatio.Optional(
                            probatio.Secret(CONF_SIGNING_KEY)
                        ): SIGNING_KEY_SELECTOR,
                    }
                ),
                # The signing key is never suggested back to the user
                {CONF_HOST: (user_input or reconfigure_entry.data)[CONF_HOST]},
            ),
            errors=errors,
        )

    async def _async_validate_host(
        self, host: str, signing_key: str | None = None
    ) -> tuple[tuple[BulbType, str] | None, dict[str, str]]:
        """Connect to the bulb and return its type and MAC, or the errors."""
        if not is_ip_address(host):
            return None, {"base": "no_ip"}
        bulb = wizlight(host, signing_key=signing_key or self._signing_key)
        try:
            bulbtype = await bulb.get_bulbtype()
            mac = await bulb.getMac()
        except WizLightTimeOutError:
            return None, {"base": "bulb_time_out"}
        except ConnectionRefusedError:
            return None, {"base": "cannot_connect"}
        except WizLightConnectionError:
            return None, {"base": "no_wiz_light"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        finally:
            await bulb.async_close()
        return (bulbtype, mac), {}

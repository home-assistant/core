"""Config flow for Apple TV integration."""
from ipaddress import ip_address
import logging
from random import randrange

from pyatv import exceptions, pair, scan
from pyatv.const import Protocol
from pyatv.convert import protocol_str
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PIN,
    CONF_PROTOCOL,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CREDENTIALS, CONF_IDENTIFIER, CONF_START_OFF
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

DEVICE_INPUT = "device_input"

INPUT_PIN_SCHEMA = vol.Schema({vol.Required(CONF_PIN, default=None): int})

DEFAULT_START_OFF = False
PROTOCOL_PRIORITY = [Protocol.MRP, Protocol.DMAP, Protocol.AirPlay]


async def device_scan(identifier, loop, cache=None):
    """Scan for a specific device using identifier as filter."""

    def _filter_device(dev):
        if identifier is None:
            return True
        if identifier == str(dev.address):
            return True
        if identifier == dev.name:
            return True
        return any([service.identifier == identifier for service in dev.services])

    def _host_filter():
        try:
            return [ip_address(identifier)]
        except ValueError:
            return None

    if cache:
        matches = [atv for atv in cache if _filter_device(atv)]
        if matches:
            return cache, matches[0]

    for hosts in [_host_filter(), None]:
        scan_result = await scan(loop, timeout=3, hosts=hosts)
        matches = [atv for atv in scan_result if _filter_device(atv)]

        if matches:
            return scan_result, matches[0]

    return scan_result, None


def is_valid_credentials(credentials):
    """Verify that credentials are valid for establishing a connection."""
    return (
        credentials.get(Protocol.MRP.value) is not None
        or credentials.get(Protocol.DMAP.value) is not None
    )


class AppleTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apple TV."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return AppleTVOptionsFlow(config_entry)

    def __init__(self):
        """Initialize a new AppleTVConfigFlow."""
        self.target_device = None
        self.scan_result = None
        self.atv = None
        self.protocol = None
        self.pairing = None
        self.credentials = {}  # Protocol -> credentials

    async def async_step_reauth(self, info):
        """Handle initial step when updating invalid credentials."""
        await self.async_set_unique_id(info[CONF_IDENTIFIER])
        self.target_device = info[CONF_IDENTIFIER]

        self.context["title_placeholders"] = {"name": info[CONF_NAME]}
        self.context["identifier"] = self.unique_id
        return await self.async_step_reconfigure()

    async def async_step_reconfigure(self, user_input=None):
        """Inform user that reconfiguration is about to start."""
        if user_input is not None:
            return await self.async_find_device_wrapper(
                self.async_begin_pairing, allow_exist=True
            )

        return self.async_show_form(step_id="reconfigure")

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # Be helpful to the user and look for devices
        if self.scan_result is None:
            self.scan_result, _ = await device_scan(None, self.hass.loop)

        errors = {}
        default_suggestion = self._prefill_identifier()
        if user_input is not None:
            self.target_device = user_input[DEVICE_INPUT]
            try:
                await self.async_find_device()
            except DeviceNotFound:
                errors["base"] = "no_devices_found"
            except DeviceAlreadyConfigured:
                errors["base"] = "already_configured"
            except exceptions.NoServiceError:
                errors["base"] = "no_usable_service"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    self.atv.identifier, raise_on_progress=False
                )
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(DEVICE_INPUT, default=default_suggestion): str}
            ),
            errors=errors,
            description_placeholders={"devices": self._devices_str()},
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle device found via zeroconf."""
        service_type = discovery_info[CONF_TYPE]
        properties = discovery_info["properties"]

        if service_type == "_mediaremotetv._tcp.local.":
            identifier = properties["UniqueIdentifier"]
            name = properties["Name"]
        elif service_type == "_touch-able._tcp.local.":
            identifier = discovery_info["name"].split(".")[0]
            name = properties["CtlN"]
        else:
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        self.context["identifier"] = self.unique_id
        self.context["title_placeholders"] = {"name": name}
        self.target_device = identifier
        return await self.async_find_device_wrapper(self.async_step_confirm)

    async def async_find_device_wrapper(self, next_func, allow_exist=False):
        """Find a specific device and call another function when done.

        This function will do error handling and bail out when an error
        occurs.
        """
        try:
            await self.async_find_device(allow_exist)
        except DeviceNotFound:
            return self.async_abort(reason="no_devices_found")
        except DeviceAlreadyConfigured:
            return self.async_abort(reason="already_configured")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return await next_func()

    async def async_find_device(self, allow_exist=False):
        """Scan for the selected device to discover services."""
        self.scan_result, self.atv = await device_scan(
            self.target_device, self.hass.loop, cache=self.scan_result
        )
        if not self.atv:
            raise DeviceNotFound()

        self.protocol = self.atv.main_service().protocol

        if not allow_exist:
            for identifier in self.atv.all_identifiers:
                if identifier in self._async_current_ids():
                    raise DeviceAlreadyConfigured()

        # If credentials were found, save them
        for service in self.atv.services:
            if service.credentials:
                self.credentials[service.protocol.value] = service.credentials

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self.async_begin_pairing()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self.atv.name}
        )

    async def async_begin_pairing(self):
        """Start pairing process for the next available protocol."""
        self.protocol = self._next_protocol_to_pair()

        # Dispose previous pairing sessions
        if self.pairing is not None:
            await self.pairing.close()
            self.pairing = None

        # Any more protocols to pair? Else bail out here
        if not self.protocol:
            await self.async_set_unique_id(self.atv.main_service().identifier)
            return self._async_get_entry(
                self.atv.main_service().protocol,
                self.atv.name,
                self.credentials,
                self.atv.address,
            )

        # Initiate the pairing process
        abort_reason = None
        session = async_get_clientsession(self.hass)
        self.pairing = await pair(
            self.atv, self.protocol, self.hass.loop, session=session
        )
        try:
            await self.pairing.begin()
        except exceptions.ConnectionFailedError:
            return await self.async_step_service_problem()
        except exceptions.BackOffError:
            abort_reason = "backoff"
        except exceptions.PairingError:
            _LOGGER.exception("Authentication problem")
            abort_reason = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            abort_reason = "unknown"

        if abort_reason:
            if self.pairing:
                await self.pairing.close()
            return self.async_abort(reason=abort_reason)

        # Choose step depending on if PIN is required from user or not
        if self.pairing.device_provides_pin:
            return await self.async_step_pair_with_pin()

        return await self.async_step_pair_no_pin()

    async def async_step_pair_with_pin(self, user_input=None):
        """Handle pairing step where a PIN is required from the user."""
        errors = {}
        if user_input is not None:
            try:
                self.pairing.pin(user_input[CONF_PIN])
                await self.pairing.finish()
                self.credentials[self.protocol.value] = self.pairing.service.credentials
                return await self.async_begin_pairing()
            except exceptions.PairingError:
                _LOGGER.exception("Authentication problem")
                errors["base"] = "invalid_auth"
            except AbortFlow:
                raise
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="pair_with_pin",
            data_schema=INPUT_PIN_SCHEMA,
            errors=errors,
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    async def async_step_pair_no_pin(self, user_input=None):
        """Handle step where user has to enter a PIN on the device."""
        if user_input is not None:
            await self.pairing.finish()
            if self.pairing.has_paired:
                self.credentials[self.protocol.value] = self.pairing.service.credentials
                return await self.async_begin_pairing()

            await self.pairing.close()
            return self.async_abort(reason="device_did_not_pair")

        pin = randrange(1000, stop=10000)
        self.pairing.pin(pin)
        return self.async_show_form(
            step_id="pair_no_pin",
            description_placeholders={
                "protocol": protocol_str(self.protocol),
                "pin": pin,
            },
        )

    async def async_step_service_problem(self, user_input=None):
        """Inform user that a service will not be added."""
        if user_input is not None:
            self.credentials[self.protocol.value] = None
            return await self.async_begin_pairing()

        return self.async_show_form(
            step_id="service_problem",
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    def _async_get_entry(self, protocol, name, credentials, address):
        if not is_valid_credentials(credentials):
            return self.async_abort(reason="invalid_config")

        data = {
            CONF_PROTOCOL: protocol.value,
            CONF_NAME: name,
            CONF_CREDENTIALS: credentials,
            CONF_ADDRESS: str(address),
        }

        self._abort_if_unique_id_configured(reload_on_update=False, updates=data)

        return self.async_create_entry(title=name, data=data)

    def _next_protocol_to_pair(self):
        def _needs_pairing(protocol):
            if self.atv.get_service(protocol) is None:
                return False
            return protocol.value not in self.credentials

        for protocol in PROTOCOL_PRIORITY:
            if _needs_pairing(protocol):
                return protocol
        return None

    def _devices_str(self):
        return ", ".join(
            [
                f"`{atv.name} ({atv.address})`"
                for atv in self.scan_result
                if atv.identifier not in self._async_current_ids()
            ]
        )

    def _prefill_identifier(self):
        # Return identifier (address) of one device that has not been paired with
        for atv in self.scan_result:
            if atv.identifier not in self._async_current_ids():
                return str(atv.address)
        return ""


class AppleTVOptionsFlow(config_entries.OptionsFlow):
    """Handle Apple TV options."""

    def __init__(self, config_entry):
        """Initialize Apple TV options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Apple TV options."""
        if user_input is not None:
            self.options[CONF_START_OFF] = user_input[CONF_START_OFF]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_START_OFF,
                        default=self.config_entry.options.get(
                            CONF_START_OFF, DEFAULT_START_OFF
                        ),
                    ): bool,
                }
            ),
        )


class DeviceNotFound(HomeAssistantError):
    """Error to indicate device could not be found."""


class DeviceAlreadyConfigured(HomeAssistantError):
    """Error to indicate device is already configured."""

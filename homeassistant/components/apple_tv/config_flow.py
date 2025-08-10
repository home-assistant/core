"""Config flow for Apple TV integration."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from ipaddress import ip_address
import logging
from random import randrange
from typing import Any, Self

from pyatv import exceptions, pair, scan
from pyatv.const import DeviceModel, PairingRequirement, Protocol
from pyatv.convert import model_str, protocol_str
from pyatv.helpers import get_unique_id
from pyatv.interface import BaseConfig, PairingHandler
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_CREDENTIALS, CONF_IDENTIFIERS, CONF_START_OFF, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_INPUT = "device_input"

INPUT_PIN_SCHEMA = vol.Schema({vol.Required(CONF_PIN, default=None): int})

DEFAULT_START_OFF = False

DISCOVERY_AGGREGATION_TIME = 15  # seconds

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_START_OFF, default=DEFAULT_START_OFF): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


async def device_scan(
    hass: HomeAssistant, identifier: str | None, loop: asyncio.AbstractEventLoop
) -> tuple[BaseConfig | None, list[str] | None]:
    """Scan for a specific device using identifier as filter."""

    def _filter_device(dev: BaseConfig) -> bool:
        if identifier is None:
            return True
        if identifier == str(dev.address):
            return True
        if identifier == dev.name:
            return True
        return any(service.identifier == identifier for service in dev.services)

    def _host_filter() -> list[str] | None:
        if identifier is None:
            return None
        try:
            ip_address(identifier)
        except ValueError:
            return None
        return [identifier]

    # If we have an address, only probe that address to avoid
    # broadcast traffic on the network
    aiozc = await zeroconf.async_get_async_instance(hass)
    scan_result = await scan(loop, timeout=3, hosts=_host_filter(), aiozc=aiozc)
    matches = [atv for atv in scan_result if _filter_device(atv)]

    if matches:
        return matches[0], matches[0].all_identifiers

    return None, None


class AppleTVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apple TV."""

    VERSION = 1

    scan_filter: str | None = None
    atv: BaseConfig | None = None
    atv_identifiers: list[str] | None = None
    _host: str  # host in zeroconf discovery info, should not be accessed by other flows
    host: str | None = None  # set by _async_aggregate_discoveries, for other flows
    protocol: Protocol | None = None
    pairing: PairingHandler | None = None
    protocols_to_pair: deque[Protocol] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    def __init__(self) -> None:
        """Initialize a new AppleTVConfigFlow."""
        self.credentials: dict[int, str | None] = {}  # Protocol -> credentials
        self.all_identifiers: set[str] = set()

    @property
    def device_identifier(self) -> str | None:
        """Return a identifier for the config entry.

        A device has multiple unique identifiers, but Home Assistant only supports one
        per config entry. Normally, a "main identifier" is determined by pyatv by
        first collecting all identifiers and then picking one in a pre-determine order.
        Under normal circumstances, this works fine but if a service is missing or
        removed due to deprecation (which happened with MRP), then another identifier
        will be calculated instead. To fix this, all identifiers belonging to a device
        is stored with the config entry and one of them (could be random) is used as
        unique_id for said entry. When a new (zeroconf) service or device is
        discovered, the identifier is first used to look up if it belongs to an
        existing config entry. If that's the case, the unique_id from that entry is
        reused, otherwise the newly discovered identifier is used instead.
        """
        assert self.atv
        all_identifiers = set(self.atv.all_identifiers)
        if unique_id := self._entry_unique_id_from_identifers(all_identifiers):
            return unique_id
        return self.atv.identifier

    @callback
    def _entry_unique_id_from_identifers(self, all_identifiers: set[str]) -> str | None:
        """Search existing entries for an identifier and return the unique id."""
        for entry in self._async_current_entries(include_ignore=True):
            if not all_identifiers.isdisjoint(
                entry.data.get(CONF_IDENTIFIERS, [entry.unique_id])
            ):
                return entry.unique_id
        return None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initial step when updating invalid credentials."""
        self.context["title_placeholders"] = {
            "name": entry_data[CONF_NAME],
            "type": "Apple TV",
        }
        self.scan_filter = self.unique_id
        return await self.async_step_restore_device()

    async def async_step_restore_device(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Inform user that reconfiguration is about to start."""
        if user_input is not None:
            return await self.async_find_device_wrapper(
                self.async_pair_next_protocol, allow_exist=True
            )

        return self.async_show_form(step_id="restore_device")

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self.scan_filter = user_input[DEVICE_INPUT]
            try:
                await self.async_find_device()
            except DeviceNotFound:
                errors["base"] = "no_devices_found"
            except DeviceAlreadyConfigured:
                errors["base"] = "already_configured"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    self.device_identifier, raise_on_progress=False
                )
                assert self.atv
                self.all_identifiers = set(self.atv.all_identifiers)
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(DEVICE_INPUT): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle device found via zeroconf."""
        if discovery_info.ip_address.version == 6:
            return self.async_abort(reason="ipv6_not_supported")
        self._host = host = discovery_info.host
        service_type = discovery_info.type[:-1]  # Remove leading .
        name = discovery_info.name.replace(f".{service_type}.", "")
        properties = discovery_info.properties

        # Extract unique identifier from service
        unique_id = get_unique_id(service_type, name, properties)
        if unique_id is None:
            return self.async_abort(reason="unknown")

        # The unique id for the zeroconf service may not be
        # the same as the unique id for the device. If the
        # device is already configured so if we don't
        # find a match here, we will fallback to
        # looking up the device by all its identifiers
        # in the next block.
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: host})

        if existing_unique_id := self._entry_unique_id_from_identifers({unique_id}):
            await self.async_set_unique_id(existing_unique_id)
            self._abort_if_unique_id_configured(updates={CONF_ADDRESS: host})

        self._async_abort_entries_match({CONF_ADDRESS: host})

        await self._async_aggregate_discoveries(host, unique_id)
        # Scan for the device in order to extract _all_ unique identifiers assigned to
        # it. Not doing it like this will yield multiple config flows for the same
        # device, one per protocol, which is undesired.
        self.scan_filter = host
        return await self.async_find_device_wrapper(self.async_found_zeroconf_device)

    async def _async_aggregate_discoveries(self, host: str, unique_id: str) -> None:
        """Wait for multiple zeroconf services to be discovered an aggregate them."""
        #
        # Suppose we have a device with three services: A, B and C. Let's assume
        # service A is discovered by Zeroconf, triggering a device scan that also finds
        # service B but *not* C. An identifier is picked from one of the services and
        # used as unique_id. The select process is deterministic (let's say in order A,
        # B and C) but in practice that doesn't matter. So, a flow is set up for the
        # device with unique_id set to "A" for services A and B.
        #
        # Now, service C is found and the same thing happens again but only service B
        # is found. In this case, unique_id will be set to "B" which is problematic
        # since both flows really represent the same device. They will however end up
        # as two separate flows.
        #
        # To solve this, all identifiers are stored as
        # "all_identifiers" in the flow. When a new service is discovered, the
        # code below will check these identifiers for all active flows and abort if a
        # match is found. Before aborting, the original flow is updated with any
        # potentially new identifiers. In the example above, when service C is
        # discovered, the identifier of service C will be inserted into
        # "all_identifiers" of the original flow (making the device complete).
        #
        # Wait DISCOVERY_AGGREGATION_TIME for multiple services to be
        # discovered via zeroconf. Once the first service is discovered
        # this allows other services to be discovered inside the time
        # window before triggering a scan of the device. This prevents
        # multiple scans of the device at the same time since each
        # apple_tv device has multiple services that are discovered by
        # zeroconf.
        #
        self._async_check_and_update_in_progress(host, unique_id)
        await asyncio.sleep(DISCOVERY_AGGREGATION_TIME)
        # Check again after sleeping in case another flow
        # has made progress while we yielded to the event loop
        self._async_check_and_update_in_progress(host, unique_id)
        # Host must only be set AFTER checking and updating in progress
        # flows or we will have a race condition where no flows move forward.
        self.host = host

    @callback
    def _async_check_and_update_in_progress(self, host: str, unique_id: str) -> None:
        """Check for in-progress flows and update them with identifiers if needed."""
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            raise AbortFlow("already_in_progress")

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        if (
            other_flow.context.get("source") != SOURCE_ZEROCONF
            or other_flow.host != self._host
        ):
            return False
        if self.unique_id is not None:
            # Add potentially new identifiers from this device to the existing flow
            other_flow.all_identifiers.add(self.unique_id)
        return True

    async def async_found_zeroconf_device(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle device found after Zeroconf discovery."""
        assert self.atv
        self.all_identifiers = set(self.atv.all_identifiers)
        # Also abort if an integration with this identifier already exists
        await self.async_set_unique_id(self.device_identifier)
        # but be sure to update the address if its changed so the scanner
        # will probe the new address
        self._abort_if_unique_id_configured(
            updates={CONF_ADDRESS: str(self.atv.address)}
        )
        return await self.async_step_confirm()

    async def async_find_device_wrapper(
        self,
        next_func: Callable[[], Awaitable[ConfigFlowResult]],
        allow_exist: bool = False,
    ) -> ConfigFlowResult:
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
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return await next_func()

    async def async_find_device(self, allow_exist: bool = False) -> None:
        """Scan for the selected device to discover services."""
        self.atv, self.atv_identifiers = await device_scan(
            self.hass, self.scan_filter, self.hass.loop
        )
        if not self.atv:
            raise DeviceNotFound

        # Protocols supported by the device are prospects for pairing
        self.protocols_to_pair = deque(
            service.protocol for service in self.atv.services if service.enabled
        )

        dev_info = self.atv.device_info
        self.context["title_placeholders"] = {
            "name": self.atv.name,
            "type": (
                dev_info.raw_model
                if dev_info.model == DeviceModel.Unknown and dev_info.raw_model
                else model_str(dev_info.model)
            ),
        }
        all_identifiers = set(self.atv.all_identifiers)
        discovered_ip_address = str(self.atv.address)
        for entry in self._async_current_entries():
            existing_identifiers = set(
                entry.data.get(CONF_IDENTIFIERS, [entry.unique_id])
            )
            if all_identifiers.isdisjoint(existing_identifiers):
                continue
            combined_identifiers = existing_identifiers | all_identifiers
            if entry.data.get(
                CONF_ADDRESS
            ) != discovered_ip_address or combined_identifiers != set(
                entry.data.get(CONF_IDENTIFIERS, [])
            ):
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_ADDRESS: discovered_ip_address,
                        CONF_IDENTIFIERS: list(combined_identifiers),
                    },
                )
                # Don't reload ignored entries or in the middle of reauth,
                # e.g. if the user is entering a new PIN
                if entry.source != SOURCE_IGNORE and self.source != SOURCE_REAUTH:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
            if not allow_exist:
                raise DeviceAlreadyConfigured

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        assert self.atv
        if user_input is not None:
            expected_identifier_count = len(self.all_identifiers)
            # If number of services found during device scan mismatch number of
            # identifiers collected during Zeroconf discovery, then trigger a new scan
            # with hopes of finding all services.
            if len(self.atv.all_identifiers) != expected_identifier_count:
                try:
                    await self.async_find_device()
                except DeviceNotFound:
                    return self.async_abort(reason="device_not_found")

            # If all services still were not found, bail out with an error
            if len(self.atv.all_identifiers) != expected_identifier_count:
                return self.async_abort(reason="inconsistent_device")

            return await self.async_pair_next_protocol()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self.atv.name,
                "type": model_str(self.atv.device_info.model),
            },
        )

    async def async_pair_next_protocol(self) -> ConfigFlowResult:
        """Start pairing process for the next available protocol."""
        await self._async_cleanup()

        # Any more protocols to pair? Else bail out here
        if not self.protocols_to_pair:
            return await self._async_get_entry()

        self.protocol = self.protocols_to_pair.popleft()
        assert self.atv
        service = self.atv.get_service(self.protocol)

        if service is None:
            _LOGGER.debug(
                "%s does not support pairing (cannot find a corresponding service)",
                self.protocol,
            )
            return await self.async_pair_next_protocol()

        # Service requires a password
        if service.requires_password:
            return await self.async_step_password()

        # Figure out, depending on protocol, what kind of pairing is needed
        if service.pairing == PairingRequirement.Unsupported:
            _LOGGER.debug("%s does not support pairing", self.protocol)
            return await self.async_pair_next_protocol()
        if service.pairing == PairingRequirement.Disabled:
            return await self.async_step_protocol_disabled()
        if service.pairing == PairingRequirement.NotNeeded:
            _LOGGER.debug("%s does not require pairing", self.protocol)
            self.credentials[self.protocol.value] = None
            return await self.async_pair_next_protocol()

        _LOGGER.debug("%s requires pairing", self.protocol)

        # Protocol specific arguments
        pair_args: dict[str, Any] = {}
        if self.protocol in {Protocol.AirPlay, Protocol.Companion, Protocol.DMAP}:
            pair_args["name"] = "Home Assistant"
        if self.protocol == Protocol.DMAP:
            pair_args["zeroconf"] = await zeroconf.async_get_instance(self.hass)

        # Initiate the pairing process
        abort_reason = None
        session = async_get_clientsession(self.hass)
        self.pairing = await pair(
            self.atv, self.protocol, self.hass.loop, session=session, **pair_args
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
        except Exception:
            _LOGGER.exception("Unexpected exception")
            abort_reason = "unknown"

        if abort_reason:
            await self._async_cleanup()
            return self.async_abort(reason=abort_reason)

        # Choose step depending on if PIN is required from user or not
        if self.pairing.device_provides_pin:
            return await self.async_step_pair_with_pin()

        return await self.async_step_pair_no_pin()

    async def async_step_protocol_disabled(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Inform user that a protocol is disabled and cannot be paired."""
        assert self.protocol
        if user_input is not None:
            return await self.async_pair_next_protocol()
        return self.async_show_form(
            step_id="protocol_disabled",
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    async def async_step_pair_with_pin(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle pairing step where a PIN is required from the user."""
        errors = {}
        assert self.pairing
        assert self.protocol
        if user_input is not None:
            try:
                self.pairing.pin(user_input[CONF_PIN])
                await self.pairing.finish()
                self.credentials[self.protocol.value] = self.pairing.service.credentials
                return await self.async_pair_next_protocol()
            except exceptions.PairingError:
                _LOGGER.exception("Authentication problem")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="pair_with_pin",
            data_schema=INPUT_PIN_SCHEMA,
            errors=errors,
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    async def async_step_pair_no_pin(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle step where user has to enter a PIN on the device."""
        assert self.pairing
        assert self.protocol
        if user_input is not None:
            await self.pairing.finish()
            if self.pairing.has_paired:
                self.credentials[self.protocol.value] = self.pairing.service.credentials
                return await self.async_pair_next_protocol()

            await self.pairing.close()
            return self.async_abort(reason="device_did_not_pair")

        pin = randrange(1000, stop=10000)
        self.pairing.pin(pin)
        return self.async_show_form(
            step_id="pair_no_pin",
            description_placeholders={
                "protocol": protocol_str(self.protocol),
                "pin": str(pin),
            },
        )

    async def async_step_service_problem(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Inform user that a service will not be added."""
        assert self.protocol
        if user_input is not None:
            return await self.async_pair_next_protocol()

        return self.async_show_form(
            step_id="service_problem",
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    async def async_step_password(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Inform user that password is not supported."""
        assert self.protocol
        if user_input is not None:
            return await self.async_pair_next_protocol()

        return self.async_show_form(
            step_id="password",
            description_placeholders={"protocol": protocol_str(self.protocol)},
        )

    async def _async_cleanup(self) -> None:
        """Clean up allocated resources."""
        if self.pairing is not None:
            await self.pairing.close()
            self.pairing = None

    async def _async_get_entry(self) -> ConfigFlowResult:
        """Return config entry or update existing config entry."""
        # Abort if no protocols were paired
        if not self.credentials:
            return self.async_abort(reason="setup_failed")

        assert self.atv

        data = {
            CONF_NAME: self.atv.name,
            CONF_CREDENTIALS: self.credentials,
            CONF_ADDRESS: str(self.atv.address),
            CONF_IDENTIFIERS: self.atv_identifiers,
        }

        existing_entry = await self.async_set_unique_id(
            self.device_identifier, raise_on_progress=False
        )

        # If an existing config entry is updated, then this was a re-auth
        if existing_entry:
            return self.async_update_reload_and_abort(
                existing_entry, data=data, unique_id=self.unique_id
            )

        return self.async_create_entry(title=self.atv.name, data=data)


class DeviceNotFound(HomeAssistantError):
    """Error to indicate device could not be found."""


class DeviceAlreadyConfigured(HomeAssistantError):
    """Error to indicate device is already configured."""

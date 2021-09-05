"""Config flow to configure homekit_controller."""
import logging
import re

import aiohomekit
from aiohomekit.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    async_get_registry as async_get_device_registry,
)

from .connection import get_accessory_name, get_bridge_information
from .const import DOMAIN, KNOWN_DEVICES

HOMEKIT_DIR = ".homekit"
HOMEKIT_BRIDGE_DOMAIN = "homekit"

HOMEKIT_IGNORE = [
    # eufy Indoor Cam 2K and 2K Pan & Tilt
    # https://github.com/home-assistant/core/issues/42307
    "T8400",
    "T8410",
    # Hive Hub - vendor does not give user a pairing code
    "HHKBridge1,1",
]

PAIRING_FILE = "pairing.json"

MDNS_SUFFIX = "._hap._tcp.local."

PIN_FORMAT = re.compile(r"^(\d{3})-{0,1}(\d{2})-{0,1}(\d{3})$")

_LOGGER = logging.getLogger(__name__)


INSECURE_CODES = {
    "00000000",
    "11111111",
    "22222222",
    "33333333",
    "44444444",
    "55555555",
    "66666666",
    "77777777",
    "88888888",
    "99999999",
    "12345678",
    "87654321",
}


def normalize_hkid(hkid):
    """Normalize a hkid so that it is safe to compare with other normalized hkids."""
    return hkid.lower()


@callback
def find_existing_host(hass, serial):
    """Return a set of the configured hosts."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("AccessoryPairingID") == serial:
            return entry


def ensure_pin_format(pin, allow_insecure_setup_codes=None):
    """
    Ensure a pin code is correctly formatted.

    Ensures a pin code is in the format 111-11-111. Handles codes with and without dashes.

    If incorrect code is entered, an exception is raised.
    """
    match = PIN_FORMAT.search(pin.strip())
    if not match:
        raise aiohomekit.exceptions.MalformedPinError(f"Invalid PIN code f{pin}")
    pin_without_dashes = "".join(match.groups())
    if not allow_insecure_setup_codes and pin_without_dashes in INSECURE_CODES:
        raise InsecureSetupCode(f"Invalid PIN code f{pin}")
    return "-".join(match.groups())


class HomekitControllerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a HomeKit config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the homekit_controller flow."""
        self.model = None
        self.hkid = None
        self.name = None
        self.devices = {}
        self.controller = None
        self.finish_pairing = None

    async def _async_setup_controller(self):
        """Create the controller."""
        async_zeroconf_instance = await zeroconf.async_get_async_instance(self.hass)
        self.controller = aiohomekit.Controller(
            async_zeroconf_instance=async_zeroconf_instance
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            key = user_input["device"]
            self.hkid = self.devices[key].device_id
            self.model = self.devices[key].info["md"]
            self.name = key[: -len(MDNS_SUFFIX)] if key.endswith(MDNS_SUFFIX) else key
            await self.async_set_unique_id(
                normalize_hkid(self.hkid), raise_on_progress=False
            )

            return await self.async_step_pair()

        if self.controller is None:
            await self._async_setup_controller()

        all_hosts = await self.controller.discover_ip()

        self.devices = {}
        for host in all_hosts:
            status_flags = int(host.info["sf"])
            paired = not status_flags & 0x01
            if paired:
                continue
            self.devices[host.info["name"]] = host

        if not self.devices:
            return self.async_abort(reason="no_devices")

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(self.devices.keys())}
            ),
        )

    async def async_step_unignore(self, user_input):
        """Rediscover a previously ignored discover."""
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)

        if self.controller is None:
            await self._async_setup_controller()

        devices = await self.controller.discover_ip(max_seconds=5)
        for device in devices:
            if normalize_hkid(device.device_id) != unique_id:
                continue
            record = device.info
            return await self.async_step_zeroconf(
                {
                    "host": record["address"],
                    "port": record["port"],
                    "hostname": record["name"],
                    "type": "_hap._tcp.local.",
                    "name": record["name"],
                    "properties": {
                        "md": record["md"],
                        "pv": record["pv"],
                        "id": unique_id,
                        "c#": record["c#"],
                        "s#": record["s#"],
                        "ff": record["ff"],
                        "ci": record["ci"],
                        "sf": record["sf"],
                        "sh": "",
                    },
                }
            )

        return self.async_abort(reason="no_devices")

    async def _hkid_is_homekit(self, hkid):
        """Determine if the device is a homekit bridge or accessory."""
        dev_reg = await async_get_device_registry(self.hass)
        device = dev_reg.async_get_device(
            identifiers=set(), connections={(CONNECTION_NETWORK_MAC, hkid)}
        )

        if device is None:
            return False

        for entry_id in device.config_entries:
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == HOMEKIT_BRIDGE_DOMAIN:
                return True

        return False

    async def async_step_zeroconf(self, discovery_info):
        """Handle a discovered HomeKit accessory.

        This flow is triggered by the discovery component.
        """
        # Normalize properties from discovery
        # homekit_python has code to do this, but not in a form we can
        # easily use, so do the bare minimum ourselves here instead.
        properties = {
            key.lower(): value for (key, value) in discovery_info["properties"].items()
        }

        if "id" not in properties:
            # This can happen if the TXT record is received after the PTR record
            # we will wait for the next update in this case
            _LOGGER.debug(
                "HomeKit device %s: id not exposed; TXT record may have not yet been received",
                properties,
            )
            return self.async_abort(reason="invalid_properties")

        # The hkid is a unique random number that looks like a pairing code.
        # It changes if a device is factory reset.
        hkid = properties["id"]
        model = properties["md"]
        name = discovery_info["name"].replace("._hap._tcp.local.", "")
        status_flags = int(properties["sf"])
        paired = not status_flags & 0x01

        # The configuration number increases every time the characteristic map
        # needs updating. Some devices use a slightly off-spec name so handle
        # both cases.
        try:
            config_num = int(properties["c#"])
        except KeyError:
            _LOGGER.warning(
                "HomeKit device %s: c# not exposed, in violation of spec", hkid
            )
            config_num = None

        # Set unique-id and error out if it's already configured
        existing_entry = await self.async_set_unique_id(normalize_hkid(hkid))
        updated_ip_port = {
            "AccessoryIP": discovery_info["host"],
            "AccessoryPort": discovery_info["port"],
        }

        # If the device is already paired and known to us we should monitor c#
        # (config_num) for changes. If it changes, we check for new entities
        if paired and hkid in self.hass.data.get(KNOWN_DEVICES, {}):
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data={**existing_entry.data, **updated_ip_port}
                )
            conn = self.hass.data[KNOWN_DEVICES][hkid]
            # When we rediscover the device, let aiohomekit know
            # that the device is available and we should not wait
            # to retry connecting any longer. reconnect_soon
            # will do nothing if the device is already connected
            await conn.pairing.connection.reconnect_soon()
            if conn.config_num != config_num:
                _LOGGER.debug(
                    "HomeKit info %s: c# incremented, refreshing entities", hkid
                )
                self.hass.async_create_task(conn.async_refresh_entity_map(config_num))
            return self.async_abort(reason="already_configured")

        _LOGGER.debug("Discovered device %s (%s - %s)", name, model, hkid)

        # Device isn't paired with us or anyone else.
        # But we have a 'complete' config entry for it - that is probably
        # invalid. Remove it automatically.
        existing = find_existing_host(self.hass, hkid)
        if not paired and existing:
            if self.controller is None:
                await self._async_setup_controller()

            pairing = self.controller.load_pairing(
                existing.data["AccessoryPairingID"], dict(existing.data)
            )
            try:
                await pairing.list_accessories_and_characteristics()
            except AuthenticationError:
                _LOGGER.debug(
                    "%s (%s - %s) is unpaired. Removing invalid pairing for this device",
                    name,
                    model,
                    hkid,
                )
                await self.hass.config_entries.async_remove(existing.entry_id)
            else:
                _LOGGER.debug(
                    "%s (%s - %s) claims to be unpaired but isn't. "
                    "It's implementation of HomeKit is defective "
                    "or a zeroconf relay is broadcasting stale data",
                    name,
                    model,
                    hkid,
                )
                return self.async_abort(reason="already_paired")

        # Set unique-id and error out if it's already configured
        self._abort_if_unique_id_configured(updates=updated_ip_port)

        self.context["hkid"] = hkid

        if paired:
            # Device is paired but not to us - ignore it
            _LOGGER.debug("HomeKit device %s ignored as already paired", hkid)
            return self.async_abort(reason="already_paired")

        # Devices in HOMEKIT_IGNORE have native local integrations - users
        # should be encouraged to use native integration and not confused
        # by alternative HK API.
        if model in HOMEKIT_IGNORE:
            return self.async_abort(reason="ignored_model")

        # If this is a HomeKit bridge/accessory exported by *this* HA instance ignore it.
        if await self._hkid_is_homekit(hkid):
            return self.async_abort(reason="ignored_model")

        self.name = name
        self.model = model
        self.hkid = hkid

        # We want to show the pairing form - but don't call async_step_pair
        # directly as it has side effects (will ask the device to show a
        # pairing code)
        return self._async_step_pair_show_form()

    async def async_step_pair(self, pair_info=None):
        """Pair with a new HomeKit accessory."""
        # If async_step_pair is called with no pairing code then we do the M1
        # phase of pairing. If this is successful the device enters pairing
        # mode.

        # If it doesn't have a screen then the pin is static.

        # If it has a display it will display a pin on that display. In
        # this case the code is random. So we have to call the start_pairing
        # API before the user can enter a pin. But equally we don't want to
        # call start_pairing when the device is discovered, only when they
        # click on 'Configure' in the UI.

        # start_pairing will make the device show its pin and return a
        # callable. We call the callable with the pin that the user has typed
        # in.

        errors = {}

        if self.controller is None:
            await self._async_setup_controller()

        if pair_info and self.finish_pairing:
            code = pair_info["pairing_code"]
            try:
                code = ensure_pin_format(
                    code,
                    allow_insecure_setup_codes=pair_info.get(
                        "allow_insecure_setup_codes"
                    ),
                )
                pairing = await self.finish_pairing(code)
                return await self._entry_from_accessory(pairing)
            except aiohomekit.exceptions.MalformedPinError:
                # Library claimed pin was invalid before even making an API call
                errors["pairing_code"] = "authentication_error"
            except aiohomekit.AuthenticationError:
                # PairSetup M4 - SRP proof failed
                # PairSetup M6 - Ed25519 signature verification failed
                # PairVerify M4 - Decryption failed
                # PairVerify M4 - Device not recognised
                # PairVerify M4 - Ed25519 signature verification failed
                errors["pairing_code"] = "authentication_error"
                self.finish_pairing = None
            except aiohomekit.UnknownError:
                # An error occurred on the device whilst performing this
                # operation.
                errors["pairing_code"] = "unknown_error"
                self.finish_pairing = None
            except aiohomekit.MaxPeersError:
                # The device can't pair with any more accessories.
                errors["pairing_code"] = "max_peers_error"
                self.finish_pairing = None
            except aiohomekit.AccessoryNotFoundError:
                # Can no longer find the device on the network
                return self.async_abort(reason="accessory_not_found_error")
            except InsecureSetupCode:
                errors["pairing_code"] = "insecure_setup_code"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Pairing attempt failed with an unhandled exception")
                self.finish_pairing = None
                errors["pairing_code"] = "pairing_failed"

        if not self.finish_pairing:
            # Its possible that the first try may have been busy so
            # we always check to see if self.finish_paring has been
            # set.
            try:
                discovery = await self.controller.find_ip_by_device_id(self.hkid)
                self.finish_pairing = await discovery.start_pairing(self.hkid)

            except aiohomekit.BusyError:
                # Already performing a pair setup operation with a different
                # controller
                return await self.async_step_busy_error()
            except aiohomekit.MaxTriesError:
                # The accessory has received more than 100 unsuccessful auth
                # attempts.
                return await self.async_step_max_tries_error()
            except aiohomekit.UnavailableError:
                # The accessory is already paired - cannot try to pair again.
                return self.async_abort(reason="already_paired")
            except aiohomekit.AccessoryNotFoundError:
                # Can no longer find the device on the network
                return self.async_abort(reason="accessory_not_found_error")
            except IndexError:
                # TLV error, usually not in pairing mode
                _LOGGER.exception("Pairing communication failed")
                return await self.async_step_protocol_error()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Pairing attempt failed with an unhandled exception")
                errors["pairing_code"] = "pairing_failed"

        return self._async_step_pair_show_form(errors)

    async def async_step_busy_error(self, user_input=None):
        """Retry pairing after the accessory is busy."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="busy_error")

    async def async_step_max_tries_error(self, user_input=None):
        """Retry pairing after the accessory has reached max tries."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="max_tries_error")

    async def async_step_protocol_error(self, user_input=None):
        """Retry pairing after the accessory has a protocol error."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="protocol_error")

    @callback
    def _async_step_pair_show_form(self, errors=None):
        placeholders = {"name": self.name}
        self.context["title_placeholders"] = {"name": self.name}

        schema = {vol.Required("pairing_code"): vol.All(str, vol.Strip)}
        if errors and errors.get("pairing_code") == "insecure_setup_code":
            schema[vol.Optional("allow_insecure_setup_codes")] = bool

        return self.async_show_form(
            step_id="pair",
            errors=errors or {},
            description_placeholders=placeholders,
            data_schema=vol.Schema(schema),
        )

    async def _entry_from_accessory(self, pairing):
        """Return a config entry from an initialized bridge."""
        # The bulk of the pairing record is stored on the config entry.
        # A specific exception is the 'accessories' key. This is more
        # volatile. We do cache it, but not against the config entry.
        # So copy the pairing data and mutate the copy.
        pairing_data = pairing.pairing_data.copy()

        # Use the accessories data from the pairing operation if it is
        # available. Otherwise request a fresh copy from the API.
        # This removes the 'accessories' key from pairing_data at
        # the same time.
        accessories = pairing_data.pop("accessories", None)
        if not accessories:
            accessories = await pairing.list_accessories_and_characteristics()

        bridge_info = get_bridge_information(accessories)
        name = get_accessory_name(bridge_info)

        return self.async_create_entry(title=name, data=pairing_data)


class InsecureSetupCode(Exception):
    """An exception for insecure trivial setup codes."""

"""Config flow to configure homekit_controller."""
import json
import logging
import os
import re

import aiohomekit
from aiohomekit.controller.ip import IpPairing
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .connection import get_accessory_name, get_bridge_information
from .const import DOMAIN, KNOWN_DEVICES

HOMEKIT_IGNORE = ["Home Assistant Bridge"]
HOMEKIT_DIR = ".homekit"
PAIRING_FILE = "pairing.json"

PIN_FORMAT = re.compile(r"^(\d{3})-{0,1}(\d{2})-{0,1}(\d{3})$")

_LOGGER = logging.getLogger(__name__)


def load_old_pairings(hass):
    """Load any old pairings from on-disk json fragments."""
    old_pairings = {}

    data_dir = os.path.join(hass.config.path(), HOMEKIT_DIR)
    pairing_file = os.path.join(data_dir, PAIRING_FILE)

    # Find any pairings created with in HA 0.85 / 0.86
    if os.path.exists(pairing_file):
        with open(pairing_file) as pairing_file:
            old_pairings.update(json.load(pairing_file))

    # Find any pairings created in HA <= 0.84
    if os.path.exists(data_dir):
        for device in os.listdir(data_dir):
            if not device.startswith("hk-"):
                continue
            alias = device[3:]
            if alias in old_pairings:
                continue
            with open(os.path.join(data_dir, device)) as pairing_data_fp:
                old_pairings[alias] = json.load(pairing_data_fp)

    return old_pairings


def normalize_hkid(hkid):
    """Normalize a hkid so that it is safe to compare with other normalized hkids."""
    return hkid.lower()


@callback
def find_existing_host(hass, serial):
    """Return a set of the configured hosts."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("AccessoryPairingID") == serial:
            return entry


def ensure_pin_format(pin):
    """
    Ensure a pin code is correctly formatted.

    Ensures a pin code is in the format 111-11-111. Handles codes with and without dashes.

    If incorrect code is entered, an exception is raised.
    """
    match = PIN_FORMAT.search(pin)
    if not match:
        raise aiohomekit.exceptions.MalformedPinError(f"Invalid PIN code f{pin}")
    return "-".join(match.groups())


@config_entries.HANDLERS.register(DOMAIN)
class HomekitControllerFlowHandler(config_entries.ConfigFlow):
    """Handle a HomeKit config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the homekit_controller flow."""
        self.model = None
        self.hkid = None
        self.devices = {}
        self.controller = aiohomekit.Controller()
        self.finish_pairing = None

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            key = user_input["device"]
            self.hkid = self.devices[key].device_id
            self.model = self.devices[key].info["md"]
            await self.async_set_unique_id(
                normalize_hkid(self.hkid), raise_on_progress=False
            )
            return await self.async_step_pair()

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

        devices = await self.controller.discover_ip(5)
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

        # If the device is already paired and known to us we should monitor c#
        # (config_num) for changes. If it changes, we check for new entities
        if paired and hkid in self.hass.data.get(KNOWN_DEVICES, {}):
            conn = self.hass.data[KNOWN_DEVICES][hkid]
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
            await self.hass.config_entries.async_remove(existing.entry_id)

        # Set unique-id and error out if it's already configured
        await self.async_set_unique_id(normalize_hkid(hkid))
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["hkid"] = hkid
        self.context["title_placeholders"] = {"name": name}

        if paired:
            old_pairings = await self.hass.async_add_executor_job(
                load_old_pairings, self.hass
            )

            if hkid in old_pairings:
                return await self.async_import_legacy_pairing(
                    properties, old_pairings[hkid]
                )

            # Device is paired but not to us - ignore it
            _LOGGER.debug("HomeKit device %s ignored as already paired", hkid)
            return self.async_abort(reason="already_paired")

        # Devices in HOMEKIT_IGNORE have native local integrations - users
        # should be encouraged to use native integration and not confused
        # by alternative HK API.
        if model in HOMEKIT_IGNORE:
            return self.async_abort(reason="ignored_model")

        self.model = model
        self.hkid = hkid

        # We want to show the pairing form - but don't call async_step_pair
        # directly as it has side effects (will ask the device to show a
        # pairing code)
        return self._async_step_pair_show_form()

    async def async_import_legacy_pairing(self, discovery_props, pairing_data):
        """Migrate a legacy pairing to config entries."""

        hkid = discovery_props["id"]

        _LOGGER.info(
            (
                "Legacy configuration %s for homekit"
                "accessory migrated to configuration entries"
            ),
            hkid,
        )

        pairing = IpPairing(pairing_data)

        return await self._entry_from_accessory(pairing)

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

        if pair_info:
            code = pair_info["pairing_code"]
            try:
                code = ensure_pin_format(code)
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
            except aiohomekit.UnknownError:
                # An error occurred on the device whilst performing this
                # operation.
                errors["pairing_code"] = "unknown_error"
            except aiohomekit.MaxPeersError:
                # The device can't pair with any more accessories.
                errors["pairing_code"] = "max_peers_error"
            except aiohomekit.AccessoryNotFoundError:
                # Can no longer find the device on the network
                return self.async_abort(reason="accessory_not_found_error")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Pairing attempt failed with an unhandled exception")
                errors["pairing_code"] = "pairing_failed"

        discovery = await self.controller.find_ip_by_device_id(self.hkid)

        try:
            self.finish_pairing = await discovery.start_pairing(self.hkid)

        except aiohomekit.BusyError:
            # Already performing a pair setup operation with a different
            # controller
            errors["pairing_code"] = "busy_error"
        except aiohomekit.MaxTriesError:
            # The accessory has received more than 100 unsuccessful auth
            # attempts.
            errors["pairing_code"] = "max_tries_error"
        except aiohomekit.UnavailableError:
            # The accessory is already paired - cannot try to pair again.
            return self.async_abort(reason="already_paired")
        except aiohomekit.AccessoryNotFoundError:
            # Can no longer find the device on the network
            return self.async_abort(reason="accessory_not_found_error")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Pairing attempt failed with an unhandled exception")
            errors["pairing_code"] = "pairing_failed"

        return self._async_step_pair_show_form(errors)

    @callback
    def _async_step_pair_show_form(self, errors=None):
        return self.async_show_form(
            step_id="pair",
            errors=errors or {},
            data_schema=vol.Schema(
                {vol.Required("pairing_code"): vol.All(str, vol.Strip)}
            ),
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

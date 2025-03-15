"""Config flow to configure homekit_controller."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Self, cast

import aiohomekit
from aiohomekit import Controller, const as aiohomekit_const
from aiohomekit.controller.abstract import (
    AbstractDiscovery,
    AbstractPairing,
    FinishPairing,
)
from aiohomekit.exceptions import AuthenticationError
from aiohomekit.model.categories import Categories
from aiohomekit.model.status_flags import StatusFlags
from aiohomekit.utils import domain_supported, domain_to_name, serialize_broadcast_key
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, KNOWN_DEVICES
from .storage import async_get_entity_storage
from .utils import async_get_controller

if TYPE_CHECKING:
    from homeassistant.components import bluetooth


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

PIN_FORMAT = re.compile(r"^(\d{3})-{0,1}(\d{2})-{0,1}(\d{3})$")

_LOGGER = logging.getLogger(__name__)


BLE_DEFAULT_NAME = "Bluetooth device"

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


def normalize_hkid(hkid: str) -> str:
    """Normalize a hkid so that it is safe to compare with other normalized hkids."""
    return hkid.lower()


def formatted_category(category: Categories) -> str:
    """Return a human readable category name."""
    return str(category.name).replace("_", " ").title()


def ensure_pin_format(pin: str, allow_insecure_setup_codes: Any = None) -> str:
    """Ensure a pin code is correctly formatted.

    Ensures a pin code is in the format 111-11-111.
    Handles codes with and without dashes.

    If incorrect code is entered, an exception is raised.
    """
    if not (match := PIN_FORMAT.search(pin.strip())):
        raise aiohomekit.exceptions.MalformedPinError(f"Invalid PIN code f{pin}")
    pin_without_dashes = "".join(match.groups())
    if not allow_insecure_setup_codes and pin_without_dashes in INSECURE_CODES:
        raise InsecureSetupCode(f"Invalid PIN code f{pin}")
    return "-".join(match.groups())


class HomekitControllerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a HomeKit config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the homekit_controller flow."""
        self.model: str | None = None
        self.hkid: str | None = None  # This is always lower case
        self.name: str | None = None
        self.category: Categories | None = None
        self.devices: dict[str, AbstractDiscovery] = {}
        self.controller: Controller | None = None
        self.finish_pairing: FinishPairing | None = None
        self.pairing = False
        self._device_paired = False

    async def _async_setup_controller(self) -> None:
        """Create the controller."""
        self.controller = await async_get_controller(self.hass)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input["device"]
            discovery = self.devices[key]
            self.category = discovery.description.category
            self.hkid = discovery.description.id
            self.model = getattr(discovery.description, "model", BLE_DEFAULT_NAME)
            self.name = discovery.description.name or BLE_DEFAULT_NAME

            await self.async_set_unique_id(
                normalize_hkid(self.hkid), raise_on_progress=False
            )

            return await self.async_step_pair()

        if self.controller is None:
            await self._async_setup_controller()

        assert self.controller

        self.devices = {}

        async for discovery in self.controller.async_discover():
            if discovery.paired:
                continue
            self.devices[discovery.description.name] = discovery

        if not self.devices:
            return self.async_abort(reason="no_devices")

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(
                        {
                            key: (
                                f"{key} ({formatted_category(discovery.description.category)})"
                            )
                            for key, discovery in self.devices.items()
                        }
                    )
                }
            ),
        )

    @callback
    def _hkid_is_homekit(self, hkid: str) -> bool:
        """Determine if the device is a homekit bridge or accessory."""
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(hkid))}
        )

        if device is None:
            return False

        for entry_id in device.config_entries:
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == HOMEKIT_BRIDGE_DOMAIN:
                return True

        return False

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered HomeKit accessory.

        This flow is triggered by the discovery component.
        """
        # Normalize properties from discovery
        # homekit_python has code to do this, but not in a form we can
        # easily use, so do the bare minimum ourselves here instead.
        properties = {
            key.lower(): value for (key, value) in discovery_info.properties.items()
        }

        if ATTR_PROPERTIES_ID not in properties:
            # This can happen if the TXT record is received after the PTR record
            # we will wait for the next update in this case
            _LOGGER.debug(
                (
                    "HomeKit device %s: id not exposed; TXT record may have not yet"
                    " been received"
                ),
                properties,
            )
            return self.async_abort(reason="invalid_properties")

        # The hkid is a unique random number that looks like a pairing code.
        # It changes if a device is factory reset.
        hkid: str = properties[ATTR_PROPERTIES_ID]
        normalized_hkid = normalize_hkid(hkid)
        upper_case_hkid = hkid.upper()
        status_flags = int(properties["sf"])
        paired = not status_flags & 0x01

        # Set unique-id and error out if it's already configured
        existing_entry = await self.async_set_unique_id(
            normalized_hkid, raise_on_progress=False
        )
        updated_ip_port = {
            "AccessoryIP": discovery_info.host,
            "AccessoryIPs": [
                str(ip_addr)
                for ip_addr in discovery_info.ip_addresses
                if not ip_addr.is_link_local and not ip_addr.is_unspecified
            ],
            "AccessoryPort": discovery_info.port,
        }
        # If the device is already paired and known to us we should monitor c#
        # (config_num) for changes. If it changes, we check for new entities
        if paired and upper_case_hkid in self.hass.data.get(KNOWN_DEVICES, {}):
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data={**existing_entry.data, **updated_ip_port}
                )
            return self.async_abort(reason="already_configured")

        # If this aiohomekit doesn't support this particular device, ignore it.
        if not domain_supported(discovery_info.name):
            return self.async_abort(reason="ignored_model")

        model = properties["md"]
        name = domain_to_name(discovery_info.name)
        _LOGGER.debug("Discovered device %s (%s - %s)", name, model, upper_case_hkid)

        # Device isn't paired with us or anyone else.
        # But we have a 'complete' config entry for it - that is probably
        # invalid. Remove it automatically if it has an accessory pairing id
        # (which means it was paired with us at some point) and was not
        # ignored by the user.
        if (
            not paired
            and existing_entry
            and (accessory_pairing_id := existing_entry.data.get("AccessoryPairingID"))
        ):
            if self.controller is None:
                await self._async_setup_controller()

            # mypy can't see that self._async_setup_controller() always
            # sets self.controller or throws
            assert self.controller

            pairing = self.controller.load_pairing(
                accessory_pairing_id, dict(existing_entry.data)
            )

            try:
                await pairing.list_accessories_and_characteristics()
            except AuthenticationError:
                _LOGGER.debug(
                    (
                        "%s (%s - %s) is unpaired. Removing invalid pairing for this"
                        " device"
                    ),
                    name,
                    model,
                    hkid,
                )
                await self.hass.config_entries.async_remove(existing_entry.entry_id)
            else:
                _LOGGER.debug(
                    (
                        "%s (%s - %s) claims to be unpaired but isn't. "
                        "It's implementation of HomeKit is defective "
                        "or a zeroconf relay is broadcasting stale data"
                    ),
                    name,
                    model,
                    hkid,
                )
                return self.async_abort(reason="already_paired")

        # Set unique-id and error out if it's already configured
        self._abort_if_unique_id_configured(updates=updated_ip_port)

        self.hkid = normalized_hkid
        self._device_paired = paired
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            raise AbortFlow("already_in_progress")

        if paired:
            # Device is paired but not to us - ignore it
            _LOGGER.debug("HomeKit device %s ignored as already paired", hkid)
            return self.async_abort(reason="already_paired")

        # Devices in HOMEKIT_IGNORE have native local integrations - users
        # should be encouraged to use native integration and not confused
        # by alternative HK API.
        if model in HOMEKIT_IGNORE:
            return self.async_abort(reason="ignored_model")

        # If this is a HomeKit bridge/accessory exported
        # by *this* HA instance ignore it.
        if self._hkid_is_homekit(hkid):
            return self.async_abort(reason="ignored_model")

        self.name = name
        self.model = model
        self.category = Categories(int(properties.get("ci", 0)))

        # We want to show the pairing form - but don't call async_step_pair
        # directly as it has side effects (will ask the device to show a
        # pairing code)
        return self._async_step_pair_show_form()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        if other_flow.context.get("unique_id") == self.hkid and not other_flow.pairing:
            if self._device_paired:
                # If the device gets paired, we want to dismiss
                # an existing discovery since we can no longer
                # pair with it
                self.hass.config_entries.flow.async_abort(other_flow.flow_id)
            else:
                return True
        return False

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        if not aiohomekit_const.BLE_TRANSPORT_SUPPORTED:
            return self.async_abort(reason="ignored_model")

        # Late imports in case BLE is not available
        # pylint: disable-next=import-outside-toplevel
        from aiohomekit.controller.ble.discovery import BleDiscovery

        # pylint: disable-next=import-outside-toplevel
        from aiohomekit.controller.ble.manufacturer_data import HomeKitAdvertisement

        mfr_data = discovery_info.manufacturer_data

        try:
            device = HomeKitAdvertisement.from_manufacturer_data(
                discovery_info.name, discovery_info.address, mfr_data
            )
        except ValueError:
            return self.async_abort(reason="ignored_model")

        await self.async_set_unique_id(normalize_hkid(device.id))
        self._abort_if_unique_id_configured()

        if not (device.status_flags & StatusFlags.UNPAIRED):
            return self.async_abort(reason="already_paired")

        if self.controller is None:
            await self._async_setup_controller()
            assert self.controller is not None

        try:
            discovery = await self.controller.async_find(device.id)
        except aiohomekit.AccessoryNotFoundError:
            return self.async_abort(reason="accessory_not_found_error")

        if TYPE_CHECKING:
            discovery = cast(BleDiscovery, discovery)

        self.name = discovery.description.name
        self.model = BLE_DEFAULT_NAME
        self.category = discovery.description.category
        self.hkid = discovery.description.id

        return self._async_step_pair_show_form()

    async def async_step_pair(
        self, pair_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pair with a new HomeKit accessory."""
        # If async_step_pair is called with no pairing code then we do the M1
        # phase of pairing. If this is successful the device enters pairing
        # mode.

        # If it doesn't have a screen then the pin is static.

        # If it has a display it will display a pin on that display. In
        # this case the code is random. So we have to call the async_start_pairing
        # API before the user can enter a pin. But equally we don't want to
        # call async_start_pairing when the device is discovered, only when they
        # click on 'Configure' in the UI.

        # async_start_pairing will make the device show its pin and return a
        # callable. We call the callable with the pin that the user has typed
        # in.

        # Should never call this step without setting self.hkid
        assert self.hkid
        description_placeholders = {}

        errors = {}

        if self.controller is None:
            await self._async_setup_controller()

        assert self.controller

        if pair_info and self.finish_pairing:
            self.pairing = True
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
            except Exception as err:
                _LOGGER.exception("Pairing attempt failed with an unhandled exception")
                self.finish_pairing = None
                errors["pairing_code"] = "pairing_failed"
                description_placeholders["error"] = str(err)

        if not self.finish_pairing:
            # Its possible that the first try may have been busy so
            # we always check to see if self.finish_paring has been
            # set.
            try:
                discovery = await self.controller.async_find(self.hkid)
                self.finish_pairing = await discovery.async_start_pairing(self.hkid)

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
            except Exception as err:
                _LOGGER.exception("Pairing attempt failed with an unhandled exception")
                errors["pairing_code"] = "pairing_failed"
                description_placeholders["error"] = str(err)

        return self._async_step_pair_show_form(errors, description_placeholders)

    async def async_step_busy_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry pairing after the accessory is busy."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="busy_error")

    async def async_step_max_tries_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry pairing after the accessory has reached max tries."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="max_tries_error")

    async def async_step_protocol_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry pairing after the accessory has a protocol error."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(step_id="protocol_error")

    @callback
    def _async_step_pair_show_form(
        self,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        assert self.category

        placeholders = self.context["title_placeholders"] = {
            "name": self.name or "Homekit Device",
            "category": formatted_category(self.category),
        }

        schema: VolDictType = {vol.Required("pairing_code"): vol.All(str, vol.Strip)}
        if errors and errors.get("pairing_code") == "insecure_setup_code":
            schema[vol.Optional("allow_insecure_setup_codes")] = bool

        return self.async_show_form(
            step_id="pair",
            errors=errors or {},
            description_placeholders=placeholders | (description_placeholders or {}),
            data_schema=vol.Schema(schema),
        )

    async def _entry_from_accessory(self, pairing: AbstractPairing) -> ConfigFlowResult:
        """Return a config entry from an initialized bridge."""
        # The bulk of the pairing record is stored on the config entry.
        # A specific exception is the 'accessories' key. This is more
        # volatile. We do cache it, but not against the config entry.
        # So copy the pairing data and mutate the copy.
        pairing_data = pairing.pairing_data.copy()  # type: ignore[attr-defined]

        # Use the accessories data from the pairing operation if it is
        # available. Otherwise request a fresh copy from the API.
        # This removes the 'accessories' key from pairing_data at
        # the same time.
        name = await pairing.get_primary_name()

        await pairing.close()

        # Save the state of the accessories so we do not
        # have to request them again when we setup the
        # config entry.
        accessories_state = pairing.accessories_state
        entity_storage = await async_get_entity_storage(self.hass)
        assert self.unique_id is not None
        entity_storage.async_create_or_update_map(
            pairing.id,
            accessories_state.config_num,
            accessories_state.accessories.serialize(),
            serialize_broadcast_key(accessories_state.broadcast_key),
            accessories_state.state_num,
        )

        return self.async_create_entry(title=name, data=pairing_data)


class InsecureSetupCode(Exception):
    """An exception for insecure trivial setup codes."""

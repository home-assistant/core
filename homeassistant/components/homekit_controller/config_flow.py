"""Config flow to configure homekit_controller."""
import os
import json
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, KNOWN_DEVICES
from .connection import get_bridge_information, get_accessory_name


HOMEKIT_IGNORE = [
    'BSB002',
    'Home Assistant Bridge',
    'TRADFRI gateway',
]
HOMEKIT_DIR = '.homekit'
PAIRING_FILE = 'pairing.json'

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
            if not device.startswith('hk-'):
                continue
            alias = device[3:]
            if alias in old_pairings:
                continue
            with open(os.path.join(data_dir, device)) as pairing_data_fp:
                old_pairings[alias] = json.load(pairing_data_fp)

    return old_pairings


@callback
def find_existing_host(hass, serial):
    """Return a set of the configured hosts."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data['AccessoryPairingID'] == serial:
            return entry


@config_entries.HANDLERS.register(DOMAIN)
class HomekitControllerFlowHandler(config_entries.ConfigFlow):
    """Handle a HomeKit config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the homekit_controller flow."""
        self.model = None
        self.hkid = None
        self.devices = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        import homekit

        errors = {}

        if user_input is not None:
            key = user_input['device']
            props = self.devices[key]['properties']
            self.hkid = props['id']
            self.model = props['md']
            return await self.async_step_pair()

        controller = homekit.Controller()
        all_hosts = await self.hass.async_add_executor_job(
            controller.discover, 5
        )

        self.devices = {}
        for host in all_hosts:
            status_flags = int(host['properties']['sf'])
            paired = not status_flags & 0x01
            if paired:
                continue
            self.devices[host['properties']['id']] = host

        if not self.devices:
            return self.async_abort(
                reason='no_devices'
            )

        return self.async_show_form(
            step_id='user',
            errors=errors,
            data_schema=vol.Schema({
                vol.Required('device'): vol.In(self.devices.keys()),
            })
        )

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered HomeKit accessory.

        This flow is triggered by the discovery component.
        """
        # Normalize properties from discovery
        # homekit_python has code to do this, but not in a form we can
        # easily use, so do the bare minimum ourselves here instead.
        properties = {
            key.lower(): value
            for (key, value) in discovery_info['properties'].items()
        }

        # The hkid is a unique random number that looks like a pairing code.
        # It changes if a device is factory reset.
        hkid = properties['id']
        model = properties['md']

        status_flags = int(properties['sf'])
        paired = not status_flags & 0x01

        # The configuration number increases every time the characteristic map
        # needs updating. Some devices use a slightly off-spec name so handle
        # both cases.
        try:
            config_num = int(properties['c#'])
        except KeyError:
            _LOGGER.warning(
                "HomeKit device %s: c# not exposed, in violation of spec",
                hkid)
            config_num = None

        if paired:
            if hkid in self.hass.data.get(KNOWN_DEVICES, {}):
                # The device is already paired and known to us
                # According to spec we should monitor c# (config_num) for
                # changes. If it changes, we check for new entities
                conn = self.hass.data[KNOWN_DEVICES][hkid]
                if conn.config_num != config_num:
                    _LOGGER.debug(
                        "HomeKit info %s: c# incremented, refreshing entities",
                        hkid)
                    self.hass.async_create_task(
                        conn.async_config_num_changed(config_num))
                return self.async_abort(reason='already_configured')

            old_pairings = await self.hass.async_add_executor_job(
                load_old_pairings,
                self.hass
            )

            if hkid in old_pairings:
                return await self.async_import_legacy_pairing(
                    properties,
                    old_pairings[hkid]
                )

            # Device is paired but not to us - ignore it
            _LOGGER.debug("HomeKit device %s ignored as already paired", hkid)
            return self.async_abort(reason='already_paired')

        # Devices in HOMEKIT_IGNORE have native local integrations - users
        # should be encouraged to use native integration and not confused
        # by alternative HK API.
        if model in HOMEKIT_IGNORE:
            return self.async_abort(reason='ignored_model')

        # Device isn't paired with us or anyone else.
        # But we have a 'complete' config entry for it - that is probably
        # invalid. Remove it automatically.
        existing = find_existing_host(self.hass, hkid)
        if existing:
            await self.hass.config_entries.async_remove(existing.entry_id)

        self.model = model
        self.hkid = hkid
        return await self.async_step_pair()

    async def async_import_legacy_pairing(self, discovery_props, pairing_data):
        """Migrate a legacy pairing to config entries."""
        from homekit.controller.ip_implementation import IpPairing

        hkid = discovery_props['id']

        existing = find_existing_host(self.hass, hkid)
        if existing:
            _LOGGER.info(
                ("Legacy configuration for homekit accessory %s"
                 "not loaded as already migrated"), hkid)
            return self.async_abort(reason='already_configured')

        _LOGGER.info(
            ("Legacy configuration %s for homekit"
             "accessory migrated to config entries"), hkid)

        pairing = IpPairing(pairing_data)

        return await self._entry_from_accessory(pairing)

    async def async_step_pair(self, pair_info=None):
        """Pair with a new HomeKit accessory."""
        import homekit  # pylint: disable=import-error

        errors = {}

        if pair_info:
            code = pair_info['pairing_code']
            controller = homekit.Controller()
            try:
                await self.hass.async_add_executor_job(
                    controller.perform_pairing, self.hkid, self.hkid, code
                )

                pairing = controller.pairings.get(self.hkid)
                if pairing:
                    return await self._entry_from_accessory(
                        pairing)

                errors['pairing_code'] = 'unable_to_pair'
            except homekit.AuthenticationError:
                errors['pairing_code'] = 'authentication_error'
            except homekit.UnknownError:
                errors['pairing_code'] = 'unknown_error'
            except homekit.UnavailableError:
                return self.async_abort(reason='already_paired')

        return self.async_show_form(
            step_id='pair',
            errors=errors,
            data_schema=vol.Schema({
                vol.Required('pairing_code'):  vol.All(str, vol.Strip),
            })
        )

    async def _entry_from_accessory(self, pairing):
        """Return a config entry from an initialized bridge."""
        accessories = await self.hass.async_add_executor_job(
            pairing.list_accessories_and_characteristics
        )
        bridge_info = get_bridge_information(accessories)
        name = get_accessory_name(bridge_info)

        return self.async_create_entry(
            title=name,
            data=pairing.pairing_data,
        )

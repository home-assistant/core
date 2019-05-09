"""Helpers for managing a pairing with a HomeKit accessory or bridge."""
import asyncio
import logging
import os

from homeassistant.helpers import discovery
from homeassistant.helpers.event import call_later

from .const import (
    CONTROLLER, DOMAIN, HOMEKIT_ACCESSORY_DISPATCH, KNOWN_DEVICES,
    PAIRING_FILE, HOMEKIT_DIR
)


RETRY_INTERVAL = 60  # seconds

_LOGGER = logging.getLogger(__name__)


def get_accessory_information(accessory):
    """Obtain the accessory information service of a HomeKit device."""
    # pylint: disable=import-error
    from homekit.model.services import ServicesTypes
    from homekit.model.characteristics import CharacteristicsTypes

    result = {}
    for service in accessory['services']:
        stype = service['type'].upper()
        if ServicesTypes.get_short(stype) != 'accessory-information':
            continue
        for characteristic in service['characteristics']:
            ctype = CharacteristicsTypes.get_short(characteristic['type'])
            if 'value' in characteristic:
                result[ctype] = characteristic['value']
    return result


def get_bridge_information(accessories):
    """Return the accessory info for the bridge."""
    for accessory in accessories:
        if accessory['aid'] == 1:
            return get_accessory_information(accessory)
    return get_accessory_information(accessories[0])


def get_accessory_name(accessory_info):
    """Return the name field of an accessory."""
    for field in ('name', 'model', 'manufacturer'):
        if field in accessory_info:
            return accessory_info[field]
    return None


class HKDevice():
    """HomeKit device."""

    def __init__(self, hass, host, port, model, hkid, config_num, config):
        """Initialise a generic HomeKit device."""
        _LOGGER.info("Setting up Homekit device %s", model)
        self.hass = hass
        self.controller = hass.data[CONTROLLER]

        self.host = host
        self.port = port
        self.model = model
        self.hkid = hkid
        self.config_num = config_num
        self.config = config
        self.configurator = hass.components.configurator
        self._connection_warning_logged = False

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities = []

        self.pairing_lock = asyncio.Lock(loop=hass.loop)

        self.pairing = self.controller.pairings.get(hkid)

        hass.data[KNOWN_DEVICES][hkid] = self

        if self.pairing is not None:
            self.accessory_setup()
        else:
            self.configure()

    def accessory_setup(self):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        from homekit.model.services import ServicesTypes
        from homekit.exceptions import AccessoryDisconnectedError

        self.pairing.pairing_data['AccessoryIP'] = self.host
        self.pairing.pairing_data['AccessoryPort'] = self.port

        try:
            data = self.pairing.list_accessories_and_characteristics()
        except AccessoryDisconnectedError:
            call_later(
                self.hass, RETRY_INTERVAL, lambda _: self.accessory_setup())
            return
        for accessory in data:
            aid = accessory['aid']
            for service in accessory['services']:
                iid = service['iid']
                if (aid, iid) in self.entities:
                    # Don't add the same entity again
                    continue

                devtype = ServicesTypes.get_short(service['type'])
                _LOGGER.debug("Found %s", devtype)
                service_info = {'serial': self.hkid,
                                'aid': aid,
                                'iid': service['iid'],
                                'model': self.model,
                                'device-type': devtype}
                component = HOMEKIT_ACCESSORY_DISPATCH.get(devtype, None)
                if component is not None:
                    discovery.load_platform(self.hass, component, DOMAIN,
                                            service_info, self.config)

    def device_config_callback(self, callback_data):
        """Handle initial pairing."""
        import homekit  # pylint: disable=import-error
        code = callback_data.get('code').strip()
        try:
            self.controller.perform_pairing(self.hkid, self.hkid, code)
        except homekit.UnavailableError:
            error_msg = "This accessory is already paired to another device. \
                         Please reset the accessory and try again."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.AuthenticationError:
            error_msg = "Incorrect HomeKit code for {}. Please check it and \
                         try again.".format(self.model)
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.UnknownError:
            error_msg = "Received an unknown error. Please file a bug."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            raise

        self.pairing = self.controller.pairings.get(self.hkid)
        if self.pairing is not None:
            pairing_dir = os.path.join(
                self.hass.config.path(),
                HOMEKIT_DIR,
            )
            if not os.path.exists(pairing_dir):
                os.makedirs(pairing_dir)
            pairing_file = os.path.join(
                pairing_dir,
                PAIRING_FILE,
            )
            self.controller.save_data(pairing_file)
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.request_done(_configurator)
            self.accessory_setup()
        else:
            error_msg = "Unable to pair, please try again"
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)

    def configure(self):
        """Obtain the pairing code for a HomeKit device."""
        description = "Please enter the HomeKit code for your {}".format(
            self.model)
        self.hass.data[DOMAIN+self.hkid] = \
            self.configurator.request_config(self.model,
                                             self.device_config_callback,
                                             description=description,
                                             submit_caption="submit",
                                             fields=[{'id': 'code',
                                                      'name': 'HomeKit code',
                                                      'type': 'string'}])

    async def get_characteristics(self, *args, **kwargs):
        """Read latest state from homekit accessory."""
        async with self.pairing_lock:
            chars = await self.hass.async_add_executor_job(
                self.pairing.get_characteristics,
                *args,
                **kwargs,
            )
        return chars

    async def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        chars = []
        for row in characteristics:
            chars.append((
                row['aid'],
                row['iid'],
                row['value'],
            ))

        async with self.pairing_lock:
            await self.hass.async_add_executor_job(
                self.pairing.put_characteristics,
                chars
            )

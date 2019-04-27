"""Helpers for managing a pairing with a HomeKit accessory or bridge."""
import asyncio
import logging
import os

from homeassistant.helpers import discovery

from .const import (
    CONTROLLER, DOMAIN, HOMEKIT_ACCESSORY_DISPATCH, KNOWN_DEVICES,
    PAIRING_FILE, HOMEKIT_DIR, ENTITY_MAP
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
        self.accessories = {}

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities = []

        self.pairing_lock = asyncio.Lock(loop=hass.loop)

        self.pairing = self.controller.pairings.get(hkid)

        hass.data[KNOWN_DEVICES][hkid] = self

    def setup(self):
        """Prepare to use a paired HomeKit device in homeassistant."""
        if self.pairing is None:
            self.configure()
            return

        self.pairing.pairing_data['AccessoryIP'] = self.host
        self.pairing.pairing_data['AccessoryPort'] = self.port

        cache = self.hass.data[ENTITY_MAP].get_map(self.unique_id)
        if not cache or cache['config_num'] < self.config_num:
            return self.refresh_entity_map(self.config_num)

        self.accessories = cache['accessories']

        # Ensure the Pairing object has access to the latest version of the
        # entity map.
        self.pairing.pairing_data['accessories'] = self.accessories

        self.add_entities()

        return True

    def refresh_entity_map(self, config_num):
        """
        Handle setup of a HomeKit accessory.

        The sync version will be removed when homekit_controller migrates to
        config flow.
        """
        self.hass.add_job(
            self.async_refresh_entity_map,
            config_num,
        )

    async def async_refresh_entity_map(self, config_num):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        from homekit.exceptions import AccessoryDisconnectedError

        try:
            self.accessories = await self.hass.async_add_executor_job(
                self.pairing.list_accessories_and_characteristics,
            )
        except AccessoryDisconnectedError:
            # If we fail to refresh this data then we will naturally retry
            # later when Bonjour spots c# is still not up to date.
            return

        self.hass.data[ENTITY_MAP].async_create_or_update_map(
            self.unique_id,
            config_num,
            self.accessories,
        )

        self.config_num = config_num

        # For BLE, the Pairing instance relies on the entity map to map
        # aid/iid to GATT characteristics. So push it to there as well.
        self.pairing.pairing_data['accessories'] = self.accessories

        # Register add new entities that are available
        await self.hass.async_add_executor_job(self.add_entities)

        return True

    def add_entities(self):
        """Process the entity map and create HA entities."""
        # pylint: disable=import-error
        from homekit.model.services import ServicesTypes

        for accessory in self.accessories:
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
                    self.entities.append((aid, iid))

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
            self.setup()
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

    @property
    def unique_id(self):
        """
        Return a unique id for this accessory or bridge.

        This id is random and will change if a device undergoes a hard reset.
        """
        return self.hkid

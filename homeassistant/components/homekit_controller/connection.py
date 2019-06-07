"""Helpers for managing a pairing with a HomeKit accessory or bridge."""
import asyncio
import logging

from .const import HOMEKIT_ACCESSORY_DISPATCH, ENTITY_MAP


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

    def __init__(self, hass, config_entry, pairing_data):
        """Initialise a generic HomeKit device."""
        from homekit.controller.ip_implementation import IpPairing

        self.hass = hass
        self.config_entry = config_entry

        # We copy pairing_data because homekit_python may mutate it, but we
        # don't want to mutate a dict owned by a config entry.
        self.pairing_data = pairing_data.copy()

        self.pairing = IpPairing(self.pairing_data)

        self.accessories = {}
        self.config_num = 0

        # A list of callbacks that turn HK service metadata into entities
        self.listeners = []

        # The platorms we have forwarded the config entry so far. If a new
        # accessory is added to a bridge we may have to load additional
        # platforms. We don't want to load all platforms up front if its just
        # a lightbulb. And we dont want to forward a config entry twice
        # (triggers a Config entry already set up error)
        self.platforms = set()

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities = []

        # There are multiple entities sharing a single connection - only
        # allow one entity to use pairing at once.
        self.pairing_lock = asyncio.Lock()

    async def async_setup(self):
        """Prepare to use a paired HomeKit device in homeassistant."""
        cache = self.hass.data[ENTITY_MAP].get_map(self.unique_id)
        if not cache:
            return await self.async_refresh_entity_map(self.config_num)

        self.accessories = cache['accessories']
        self.config_num = cache['config_num']

        # Ensure the Pairing object has access to the latest version of the
        # entity map.
        self.pairing.pairing_data['accessories'] = self.accessories

        self.async_load_platforms()

        self.add_entities()

        return True

    async def async_refresh_entity_map(self, config_num):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        from homekit.exceptions import AccessoryDisconnectedError

        try:
            async with self.pairing_lock:
                self.accessories = await self.hass.async_add_executor_job(
                    self.pairing.list_accessories_and_characteristics
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

        self.async_load_platforms()

        # Register and add new entities that are available
        self.add_entities()

        return True

    def add_listener(self, add_entities_cb):
        """Add a callback to run when discovering new entities."""
        self.listeners.append(add_entities_cb)
        self._add_new_entities([add_entities_cb])

    def add_entities(self):
        """Process the entity map and create HA entities."""
        self._add_new_entities(self.listeners)

    def _add_new_entities(self, callbacks):
        from homekit.model.services import ServicesTypes

        for accessory in self.accessories:
            aid = accessory['aid']
            for service in accessory['services']:
                iid = service['iid']
                stype = ServicesTypes.get_short(service['type'].upper())
                service['stype'] = stype

                if (aid, iid) in self.entities:
                    # Don't add the same entity again
                    continue

                for listener in callbacks:
                    if listener(aid, service):
                        self.entities.append((aid, iid))
                        break

    def async_load_platforms(self):
        """Load any platforms needed by this HomeKit device."""
        from homekit.model.services import ServicesTypes

        for accessory in self.accessories:
            for service in accessory['services']:
                stype = ServicesTypes.get_short(service['type'].upper())
                if stype not in HOMEKIT_ACCESSORY_DISPATCH:
                    continue

                platform = HOMEKIT_ACCESSORY_DISPATCH[stype]
                if platform in self.platforms:
                    continue

                self.hass.async_create_task(
                    self.hass.config_entries.async_forward_entry_setup(
                        self.config_entry,
                        platform,
                    )
                )
                self.platforms.add(platform)

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
        return self.pairing_data['AccessoryPairingID']

    @property
    def connection_info(self):
        """Return accessory information for the main accessory."""
        return get_bridge_information(self.accessories)

    @property
    def name(self):
        """Name of the bridge accessory."""
        return get_accessory_name(self.connection_info) or self.unique_id

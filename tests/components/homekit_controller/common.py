"""Code to support homekit_controller tests."""
from datetime import timedelta
from unittest import mock

from homekit.model.services import AbstractService, ServicesTypes
from homekit.model.characteristics import (
    AbstractCharacteristic, CharacteristicPermissions, CharacteristicsTypes)
from homekit.model import Accessory, get_id
from homekit.exceptions import AccessoryNotFoundError
from homeassistant.components.homekit_controller import (
    DOMAIN, HOMEKIT_ACCESSORY_DISPATCH, SERVICE_HOMEKIT)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from tests.common import async_fire_time_changed, fire_service_discovered


class FakePairing:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Pairing
    class.
    """

    def __init__(self, accessories):
        """Create a fake pairing from an accessory model."""
        self.accessories = accessories
        self.pairing_data = {}
        self.available = True

    def list_accessories_and_characteristics(self):
        """Fake implementation of list_accessories_and_characteristics."""
        accessories = [
            a.to_accessory_and_service_list() for a in self.accessories
        ]
        # replicate what happens upstream right now
        self.pairing_data['accessories'] = accessories
        return accessories

    def get_characteristics(self, characteristics):
        """Fake implementation of get_characteristics."""
        if not self.available:
            raise AccessoryNotFoundError('Accessory not found')

        results = {}
        for aid, cid in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        results[(aid, cid)] = {
                            'value': char.get_value()
                        }
        return results

    def put_characteristics(self, characteristics):
        """Fake implementation of put_characteristics."""
        for aid, cid, new_val in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        char.set_value(new_val)


class FakeController:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Controller
    class.
    """

    def __init__(self):
        """Create a Fake controller with no pairings."""
        self.pairings = {}

    def add(self, accessories):
        """Create and register a fake pairing for a simulated accessory."""
        pairing = FakePairing(accessories)
        self.pairings['00:00:00:00:00:00'] = pairing
        return pairing


class Helper:
    """Helper methods for interacting with HomeKit fakes."""

    def __init__(self, hass, entity_id, pairing, accessory):
        """Create a helper for a given accessory/entity."""
        self.hass = hass
        self.entity_id = entity_id
        self.pairing = pairing
        self.accessory = accessory

        self.characteristics = {}
        for service in self.accessory.services:
            service_name = ServicesTypes.get_short(service.type)
            for char in service.characteristics:
                char_name = CharacteristicsTypes.get_short(char.type)
                self.characteristics[(service_name, char_name)] = char

    async def poll_and_get_state(self):
        """Trigger a time based poll and return the current entity state."""
        next_update = dt_util.utcnow() + timedelta(seconds=60)
        async_fire_time_changed(self.hass, next_update)
        await self.hass.async_block_till_done()

        state = self.hass.states.get(self.entity_id)
        assert state is not None
        return state


class FakeCharacteristic(AbstractCharacteristic):
    """
    A model of a generic HomeKit characteristic.

    Base is abstract and can't be instanced directly so this subclass is
    needed even though it doesn't add any methods.
    """

    pass


class FakeService(AbstractService):
    """A model of a generic HomeKit service."""

    def __init__(self, service_name):
        """Create a fake service by its short form HAP spec name."""
        char_type = ServicesTypes.get_uuid(service_name)
        super().__init__(char_type, get_id())

    def add_characteristic(self, name):
        """Add a characteristic to this service by name."""
        full_name = 'public.hap.characteristic.' + name
        char = FakeCharacteristic(get_id(), full_name, None)
        char.perms = [
            CharacteristicPermissions.paired_read,
            CharacteristicPermissions.paired_write
        ]
        self.characteristics.append(char)
        return char


async def setup_platform(hass):
    """Load the platform but with a fake Controller API."""
    config = {
        'discovery': {
        }
    }

    with mock.patch('homekit.Controller') as controller:
        fake_controller = controller.return_value = FakeController()
        await async_setup_component(hass, DOMAIN, config)

    return fake_controller


async def setup_test_component(hass, services, capitalize=False, suffix=None):
    """Load a fake homekit accessory based on a homekit accessory model.

    If capitalize is True, property names will be in upper case.

    If suffix is set, entityId will include the suffix
    """
    domain = None
    for service in services:
        service_name = ServicesTypes.get_short(service.type)
        if service_name in HOMEKIT_ACCESSORY_DISPATCH:
            domain = HOMEKIT_ACCESSORY_DISPATCH[service_name]
            break

    assert domain, 'Cannot map test homekit services to homeassistant domain'

    fake_controller = await setup_platform(hass)

    accessory = Accessory('TestDevice', 'example.com', 'Test', '0001', '0.1')
    accessory.services.extend(services)
    pairing = fake_controller.add([accessory])

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            ('MD' if capitalize else 'md'): 'TestDevice',
            ('ID' if capitalize else 'id'): '00:00:00:00:00:00',
            ('C#' if capitalize else 'c#'): 1,
        }
    }

    fire_service_discovered(hass, SERVICE_HOMEKIT, discovery_info)
    await hass.async_block_till_done()

    entity = 'testdevice' if suffix is None else 'testdevice_{}'.format(suffix)
    return Helper(hass, '.'.join((domain, entity)), pairing, accessory)

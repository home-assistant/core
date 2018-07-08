"""
ZiGate component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ZiGate/
"""
import logging
import voluptuous as vol
import os

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import (ATTR_BATTERY_LEVEL, CONF_PORT,
                                 EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['zigate==0.17.3']
DEPENDENCIES = ['persistent_notification']

DOMAIN = 'zigate'
DATA_ZIGATE_DEVICES = 'zigate_devices'
DATA_ZIGATE_ATTRS = 'zigate_attributes'
ADDR = 'addr'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT): cv.string,
}, extra=vol.ALLOW_EXTRA)


REFRESH_DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ADDR): cv.string,
})

RAW_COMMAND_SCHEMA = vol.Schema({
    vol.Required('cmd'): cv.positive_int,
    vol.Optional('data'): cv.string,
})

IDENTIFY_SCHEMA = vol.Schema({
    vol.Required(ADDR): cv.string,
})


def setup(hass, config):
    """Setup zigate platform."""
    from homeassistant.components import persistent_notification
    import zigate

    port = config.get(CONF_PORT)
    persistent_file = os.path.join(hass.config.config_dir,
                                   'zigate.json')
    _LOGGER.debug('Persistent file {}'.format(persistent_file))

    z = zigate.ZiGate(port,
                      persistent_file,
                      auto_start=False)

    hass.data[DOMAIN] = z
    hass.data[DATA_ZIGATE_DEVICES] = {}
    hass.data[DATA_ZIGATE_ATTRS] = {}

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    def device_added(**kwargs):
        device = kwargs['device']
        _LOGGER.debug('Add device {}'.format(device))
        if device.addr not in hass.data[DATA_ZIGATE_DEVICES]:
            entity = ZiGateDeviceEntity(device)
            hass.data[DATA_ZIGATE_DEVICES][device.addr] = entity
            component.add_entities([entity])
            if 'signal' in kwargs:
                persistent_notification.create(hass,
                                               ('A new ZiGate device "{}"'
                                                ' has been added !'
                                                ).format(device),
                                               title='ZiGate')

    def device_removed(**kwargs):
        # component.async_remove_entity
        pass

    def device_need_refresh(**kwargs):
        device = kwargs['device']
        persistent_notification.create(hass,
                                       ('The ZiGate device {} needs some'
                                        ' refresh (missing important'
                                        ' information)').format(device.addr),
                                       title='ZiGate')

    zigate.dispatcher.connect(device_added,
                              zigate.ZIGATE_DEVICE_ADDED, weak=False)
    zigate.dispatcher.connect(device_removed,
                              zigate.ZIGATE_DEVICE_REMOVED, weak=False)
    zigate.dispatcher.connect(device_need_refresh,
                              zigate.ZIGATE_DEVICE_NEED_REFRESH, weak=False)

    def attribute_updated(**kwargs):
        device = kwargs['device']
        attribute = kwargs['attribute']
        _LOGGER.debug('Update attribute for device {} {}'.format(device,
                                                                 attribute))
        key = '{}-{}-{}-{}'.format(device.addr,
                                   attribute['endpoint'],
                                   attribute['cluster'],
                                   attribute['attribute'],
                                   )
        entity = hass.data[DATA_ZIGATE_ATTRS].get(key)
        if entity:
            if entity.hass:
                entity.schedule_update_ha_state()
        key = '{}-{}-{}'.format(device.addr,
                                'switch',
                                attribute['endpoint'],
                                )
        entity = hass.data[DATA_ZIGATE_ATTRS].get(key)
        if entity:
            if entity.hass:
                entity.schedule_update_ha_state()
        key = '{}-{}-{}'.format(device.addr,
                                'light',
                                attribute['endpoint'],
                                )
        entity = hass.data[DATA_ZIGATE_ATTRS].get(key)
        if entity:
            if entity.hass:
                entity.schedule_update_ha_state()
        entity = hass.data[DATA_ZIGATE_DEVICES].get(device.addr)
        if entity:
            if entity.hass:
                entity.schedule_update_ha_state()

    zigate.dispatcher.connect(attribute_updated,
                              zigate.ZIGATE_ATTRIBUTE_UPDATED, weak=False)

    def device_updated(**kwargs):
        device = kwargs['device']
        _LOGGER.debug('Update device {}'.format(device))
        entity = hass.data[DATA_ZIGATE_DEVICES].get(device.addr)
        if entity:
            if entity.hass:
                entity.schedule_update_ha_state()
        else:
            _LOGGER.debug('Device not found {}, adding it'.format(device))
            device_added(device=device)

        zigate.dispatcher.connect(device_updated,
                                  zigate.ZIGATE_DEVICE_UPDATED, weak=False)
        zigate.dispatcher.connect(device_updated,
                                  zigate.ZIGATE_ATTRIBUTE_ADDED, weak=False)

    def zigate_reset(service):
        z.reset()

    def permit_join(service):
        z.permit_join()

    def zigate_cleanup(service):
        '''
        Remove missing device
        '''
        z.cleanup_devices()

    def start_zigate(service_event):
        z.autoStart()
        z.start_auto_save()
        # firt load
        for device in z.devices:
            device_added(device=device)

        load_platform(hass, 'sensor', DOMAIN, {}, config)
        load_platform(hass, 'binary_sensor', DOMAIN, {}, config)
        load_platform(hass, 'switch', DOMAIN, {}, config)
        load_platform(hass, 'light', DOMAIN, {}, config)

    def stop_zigate(service_event):
        z.save_state()
        z.close()

    def refresh_device(service):
        addr = service.data.get(ADDR)
        if addr:
            z.refresh_device(addr)
        else:
            for device in z.devices:
                device.refresh_device()

    def network_scan(service):
        z.start_network_scan()

    def raw_command(service):
        cmd = service.data.get('cmd')
        data = service.data.get('data', '')
        z.send_data(cmd, data)

    def identify_device(service):
        addr = service.data.get('addr')
        z.identify_device(addr)

    def initiate_touchlink(service):
        z.initiate_touchlink()

    def touchlink_factory_reset(service):
        z.touchlink_factory_reset()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_zigate)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zigate)

    hass.services.register(DOMAIN, 'reset', zigate_reset)
    hass.services.register(DOMAIN, 'permit_join', permit_join)
    hass.services.register(DOMAIN, 'start_zigate', start_zigate)
    hass.services.register(DOMAIN, 'stop_zigate', stop_zigate)
    hass.services.register(DOMAIN, 'cleanup_devices', zigate_cleanup)
    hass.services.register(DOMAIN, 'refresh_device',
                           refresh_device,
                           schema=REFRESH_DEVICE_SCHEMA)
    hass.services.register(DOMAIN, 'network_scan', network_scan)
    hass.services.register(DOMAIN, 'raw_command', raw_command,
                           schema=RAW_COMMAND_SCHEMA)
    hass.services.register(DOMAIN, 'identify_device', identify_device,
                           schema=IDENTIFY_SCHEMA)
    hass.services.register(DOMAIN, 'initiate_touchlink', initiate_touchlink)
    hass.services.register(DOMAIN, 'touchlink_factory_reset',
                           touchlink_factory_reset)

    return True


class ZiGateDeviceEntity(Entity):
    '''Representation of ZiGate device'''

    def __init__(self, device):
        """Initialize the sensor."""
        self._device = device
        self._name = self._device.addr
        self.registry_name = str(device)

    @property
    def should_poll(self):
        """No polling."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.info.get('last_seen')

    @property
    def unique_id(self)->str:
        return self._device.ieee

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {'battery': self._device.get_value('battery'),
                 ATTR_BATTERY_LEVEL: int(self._device.battery_percent),
                 'rssi_percent': int(self._device.rssi_percent),
                 'type': self._device.get_value('type'),
                 'manufacturer': self._device.get_value('manufacturer'),
                 'receiver_on_when_idle': self._device.receiver_on_when_idle(),
                 'missing': self._device.missing
                 }
        attrs.update(self._device.info)
        return attrs

    @property
    def icon(self):
        if self._device.missing:
            return 'mdi:emoticon-dead'
        return 'mdi:access-point'

"""
Support for ZigBee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import collections
import enum
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import const as ha_const
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers import discovery, entity
from homeassistant.util import slugify

REQUIREMENTS = [
    'bellows==0.6.0',
    'zigpy==0.1.0',
    'zigpy-xbee==0.1.1',
]

DOMAIN = 'zha'
SWITCH = 'switch'
DEVICE = 'device'
LEVEL = 'level'
DATA_ZHA_EVENT = 'zha_events'
OFF_EVENT_KEY = 'zha.off'
ON_EVENT_KEY = 'zha.on'
TOGGLE_EVENT_KEY = 'zha.toggle'
LEVEL_CHANGE_EVENT_KEY = 'zha.level_change'


class RadioType(enum.Enum):
    """Possible options for radio type in config."""

    ezsp = 'ezsp'
    xbee = 'xbee'


CONF_BAUDRATE = 'baudrate'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
CONF_RADIO_TYPE = 'radio_type'
CONF_USB_PATH = 'usb_path'
DATA_DEVICE_CONFIG = 'zha_device_config'

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(ha_const.CONF_TYPE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_RADIO_TYPE, default='ezsp'): cv.enum(RadioType),
        CONF_USB_PATH: cv.string,
        vol.Optional(CONF_BAUDRATE, default=57600): cv.positive_int,
        CONF_DATABASE: cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_DURATION = 'duration'
ATTR_IEEE = 'ieee_address'

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(1, 254)),
    }),
    SERVICE_REMOVE: vol.Schema({
        vol.Required(ATTR_IEEE): cv.string,
    }),
}


# ZigBee definitions
CENTICELSIUS = 'C-100'
# Key in hass.data dict containing discovery info
DISCOVERY_KEY = 'zha_discovery_info'

# Internal definitions
APPLICATION_CONTROLLER = None
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """
    global APPLICATION_CONTROLLER

    usb_path = config[DOMAIN].get(CONF_USB_PATH)
    baudrate = config[DOMAIN].get(CONF_BAUDRATE)
    radio_type = config[DOMAIN].get(CONF_RADIO_TYPE)
    if radio_type == RadioType.ezsp:
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication
        radio = bellows.ezsp.EZSP()
    elif radio_type == RadioType.xbee:
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication
        radio = zigpy_xbee.api.XBee()

    await radio.connect(usb_path, baudrate)

    database = config[DOMAIN].get(CONF_DATABASE)
    APPLICATION_CONTROLLER = ControllerApplication(radio, database)
    listener = ApplicationListener(hass, config)
    APPLICATION_CONTROLLER.add_listener(listener)
    await APPLICATION_CONTROLLER.startup(auto_form=True)

    for device in APPLICATION_CONTROLLER.devices.values():
        hass.async_add_job(listener.async_device_initialized(device, False))

    async def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        await APPLICATION_CONTROLLER.permit(duration)

    hass.services.async_register(DOMAIN, SERVICE_PERMIT, permit,
                                 schema=SERVICE_SCHEMAS[SERVICE_PERMIT])

    async def remove(service):
        """Remove a node from the network."""
        from bellows.types import EmberEUI64, uint8_t
        ieee = service.data.get(ATTR_IEEE)
        ieee = EmberEUI64([uint8_t(p, base=16) for p in ieee.split(':')])
        _LOGGER.info("Removing node %s", ieee)
        await APPLICATION_CONTROLLER.remove(ieee)

    hass.services.async_register(DOMAIN, SERVICE_REMOVE, remove,
                                 schema=SERVICE_SCHEMAS[SERVICE_REMOVE])

    hass.data[DATA_ZHA_EVENT] = []

    return True


class ApplicationListener:
    """All handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config
        self._device_registry = collections.defaultdict(list)
        hass.data[DISCOVERY_KEY] = hass.data.get(DISCOVERY_KEY, {})

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address
        """
        # Wait for device_initialized, instead
        pass

    def raw_device_initialized(self, device):
        """Handle a device initialization without quirks loaded."""
        # Wait for device_initialized, instead
        pass

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self._hass.async_add_job(self.async_device_initialized(device, True))

    def device_left(self, device):
        """Handle device leaving the network."""
        pass

    def device_removed(self, device):
        """Handle device being removed from the network."""
        for device_entity in self._device_registry[device.ieee]:
            self._hass.async_add_job(device_entity.async_remove())

    async def async_device_initialized(self, device, join):
        """Handle device joined and basic information discovered (async)."""
        import zigpy.profiles
        import homeassistant.components.zha.const as zha_const
        zha_const.populate_data()

        for endpoint_id, endpoint in device.endpoints.items():
            if endpoint_id == 0:  # ZDO
                continue

            discovered_info = await _discover_endpoint_info(endpoint)

            component = None
            profile_clusters = ([], [])
            device_key = "{}-{}".format(device.ieee, endpoint_id)
            node_config = self._config[DOMAIN][CONF_DEVICE_CONFIG].get(
                device_key, {})

            if endpoint.profile_id in zigpy.profiles.PROFILES:
                profile = zigpy.profiles.PROFILES[endpoint.profile_id]
                if zha_const.DEVICE_CLASS.get(endpoint.profile_id,
                                              {}).get(endpoint.device_type,
                                                      None):
                    profile_clusters = profile.CLUSTERS[endpoint.device_type]
                    profile_info = zha_const.DEVICE_CLASS[endpoint.profile_id]
                    component = profile_info[endpoint.device_type]

            if ha_const.CONF_TYPE in node_config:
                component = node_config[ha_const.CONF_TYPE]
                profile_clusters = zha_const.COMPONENT_CLUSTERS[component]

            if component:
                in_clusters = [endpoint.in_clusters[c]
                               for c in profile_clusters[0]
                               if c in endpoint.in_clusters]
                out_clusters = [endpoint.out_clusters[c]
                                for c in profile_clusters[1]
                                if c in endpoint.out_clusters]
                discovery_info = {
                    'application_listener': self,
                    'endpoint': endpoint,
                    'in_clusters': {c.cluster_id: c for c in in_clusters},
                    'out_clusters': {c.cluster_id: c for c in out_clusters},
                    'new_join': join,
                    'unique_id': device_key,
                }
                discovery_info.update(discovered_info)
                self._hass.data[DISCOVERY_KEY][device_key] = discovery_info

                from zigpy.zcl.clusters.general import OnOff
                if component == 'binary_sensor' and OnOff.cluster_id in \
                        discovery_info['out_clusters']:
                    await self._async_setup_remote(discovery_info)
                else:
                    await discovery.async_load_platform(
                        self._hass,
                        component,
                        DOMAIN,
                        {'discovery_key': device_key},
                        self._config,
                    )

            for cluster in endpoint.in_clusters.values():
                await self._attempt_single_cluster_device(
                    endpoint,
                    cluster,
                    profile_clusters[0],
                    device_key,
                    zha_const.SINGLE_INPUT_CLUSTER_DEVICE_CLASS,
                    'in_clusters',
                    discovered_info,
                    join,
                )

            for cluster in endpoint.out_clusters.values():
                await self._attempt_single_cluster_device(
                    endpoint,
                    cluster,
                    profile_clusters[1],
                    device_key,
                    zha_const.SINGLE_OUTPUT_CLUSTER_DEVICE_CLASS,
                    'out_clusters',
                    discovered_info,
                    join,
                )

    def register_entity(self, ieee, entity_obj):
        """Record the creation of a hass entity associated with ieee."""
        self._device_registry[ieee].append(entity_obj)

    async def _attempt_single_cluster_device(self, endpoint, cluster,
                                             profile_clusters, device_key,
                                             device_classes, discovery_attr,
                                             entity_info, is_new_join):
        """Try to set up an entity from a "bare" cluster."""
        if cluster.cluster_id in profile_clusters:
            return

        component = None
        for cluster_type, candidate_component in device_classes.items():
            if isinstance(cluster, cluster_type):
                component = candidate_component
                break

        if component is None:
            return

        cluster_key = "{}-{}".format(device_key, cluster.cluster_id)
        discovery_info = {
            'application_listener': self,
            'endpoint': endpoint,
            'in_clusters': {},
            'out_clusters': {},
            'new_join': is_new_join,
            'unique_id': cluster_key,
            'entity_suffix': '_{}'.format(cluster.cluster_id),
        }
        discovery_info[discovery_attr] = {cluster.cluster_id: cluster}
        discovery_info.update(entity_info)
        self._hass.data[DISCOVERY_KEY][cluster_key] = discovery_info

        from zigpy.zcl.clusters.general import OnOff
        if component == 'binary_sensor' and OnOff.cluster_id == \
                cluster.cluster_id:
            await self._async_setup_remote(discovery_info)
        else:
            await discovery.async_load_platform(
                self._hass,
                component,
                DOMAIN,
                {'discovery_key': cluster_key},
                self._config,
            )

    async def _async_setup_remote(self, discovery_info):

        async def safe(coro):
            """Run coro, catching ZigBee delivery errors, and ignoring them."""
            import zigpy.exceptions
            try:
                await coro
            except zigpy.exceptions.DeliveryError as exc:
                _LOGGER.warning("Ignoring error during setup: %s", exc)

        from zigpy.zcl.clusters.general import OnOff, LevelControl
        out_clusters = discovery_info['out_clusters']
        if OnOff.cluster_id in out_clusters:
            cluster = out_clusters[OnOff.cluster_id]
            if discovery_info['new_join']:
                await safe(cluster.bind())
                await safe(cluster.configure_reporting(0, 0, 600, 1))
            self._hass.data[DATA_ZHA_EVENT].append(
                ZHASwitchEvent(self._hass, cluster, discovery_info)
            )
        if LevelControl.cluster_id in out_clusters:
            cluster = out_clusters[LevelControl.cluster_id]
            if discovery_info['new_join']:
                await safe(cluster.bind())
                await safe(cluster.configure_reporting(0, 1, 600, 1))
            self._hass.data[DATA_ZHA_EVENT].append(
                ZHALevelEvent(self._hass, cluster, discovery_info)
            )


class Entity(entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, endpoint, in_clusters, out_clusters, manufacturer,
                 model, application_listener, unique_id, **kwargs):
        """Init ZHA entity."""
        self._device_state_attributes = {}
        ieee = endpoint.device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        if manufacturer and model is not None:
            self.entity_id = "{}.{}_{}_{}_{}{}".format(
                self._domain,
                slugify(manufacturer),
                slugify(model),
                ieeetail,
                endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )
            self._device_state_attributes['friendly_name'] = "{} {}".format(
                manufacturer,
                model,
            )
        else:
            self.entity_id = "{}.zha_{}_{}{}".format(
                self._domain,
                ieeetail,
                endpoint.endpoint_id,
                kwargs.get('entity_suffix', ''),
            )

        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._state = None
        self._unique_id = unique_id

        # Normally the entity itself is the listener. Sub-classes may set this
        # to a dict of cluster ID -> listener to receive messages for specific
        # clusters separately
        self._in_listeners = {}
        self._out_listeners = {}

        application_listener.register_entity(ieee, self)

    async def async_added_to_hass(self):
        """Callback once the entity is added to hass.

        It is now safe to update the entity state
        """
        for cluster_id, cluster in self._in_clusters.items():
            cluster.add_listener(self._in_listeners.get(cluster_id, self))
        for cluster_id, cluster in self._out_clusters.items():
            cluster.add_listener(self._out_listeners.get(cluster_id, self))

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    def attribute_updated(self, attribute, value):
        """Handle an attribute updated on this cluster."""
        pass

    def zdo_command(self, tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        pass


class ZHAEvent(object):
    """When you want signals instead of entities.
    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, cluster, domain, discovery_info):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._cluster = cluster
        self._cluster.add_listener(self)
        ieee = discovery_info['endpoint'].device.ieee
        ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
        if discovery_info['manufacturer'] and discovery_info['model'] is not \
                None:
            self._id = "{}.{}_{}_{}_{}{}".format(
                domain,
                slugify(discovery_info['manufacturer']),
                slugify(discovery_info['model']),
                ieeetail,
                discovery_info['endpoint'].endpoint_id,
                discovery_info.get('entity_suffix', '')
            )
        else:
            self._id = "{}.zha_{}_{}{}".format(
                domain,
                ieeetail,
                discovery_info['endpoint'].endpoint_id,
                discovery_info.get('entity_suffix', '')
            )


class ZHASwitchEvent(ZHAEvent):
    """Switch / remote event for zha"""

    def __init__(self, hass, cluster, discovery_info):
        """Initialize Switch."""
        super().__init__(hass, cluster, SWITCH, discovery_info)

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id in (0x0000, 0x0040):
            self._hass.bus.fire(
                OFF_EVENT_KEY,
                {DEVICE: self._id},
                EventOrigin.remote
            )
        elif command_id in (0x0001, 0x0041, 0x0042):
            self._hass.bus.fire(
                ON_EVENT_KEY,
                {DEVICE: self._id},
                EventOrigin.remote
            )
        elif command_id == 0x0002:
            self._hass.bus.fire(
                TOGGLE_EVENT_KEY,
                {DEVICE: self._id},
                EventOrigin.remote
            )


class ZHALevelEvent(ZHAEvent):
    """Switch / remote event for zha"""

    def __init__(self, hass, cluster, discovery_info):
        """Initialize Switch."""
        super().__init__(hass, cluster, SWITCH, discovery_info)
        self._level = 0

    @callback
    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id in (0x0000, 0x0004):  # move_to_level, -with_on_off
            self.set_level(args[0])
        elif command_id in (0x0001, 0x0005):  # move, -with_on_off
            # We should dim slowly -- for now, just step once
            rate = args[1]
            if args[0] == 0xff:
                rate = 10  # Should read default move rate
            self.move_level(-rate if args[0] else rate)
        elif command_id == 0x0002:  # step
            # Step (technically shouldn't change on/off)
            self.move_level(-args[1] if args[0] else args[1])

    def attribute_update(self, attrid, value):
        """Handle attribute updates on this cluster."""
        if attrid == 0:
            self._level = value

    def move_level(self, change):
        """Increment the level."""
        self.set_level(min(255, max(0, self._level + change)))

    def set_level(self, level):
        """Set the level."""
        if level == 0 and self._level > 0:
            self._hass.bus.fire(
                OFF_EVENT_KEY,
                {DEVICE: self._id},
                EventOrigin.remote
            )
        elif level > 0 and self._level == 0:
            self._hass.bus.fire(
                ON_EVENT_KEY,
                {DEVICE: self._id},
                EventOrigin.remote
            )
        self._level = level
        self._hass.bus.fire(
            LEVEL_CHANGE_EVENT_KEY,
            {DEVICE: self._id, LEVEL: self._level},
            EventOrigin.remote
        )


async def _discover_endpoint_info(endpoint):
    """Find some basic information about an endpoint."""
    extra_info = {
        'manufacturer': None,
        'model': None,
    }
    if 0 not in endpoint.in_clusters:
        return extra_info

    async def read(attributes):
        """Read attributes and update extra_info convenience function."""
        result, _ = await endpoint.in_clusters[0].read_attributes(
            attributes,
            allow_cache=True,
        )
        extra_info.update(result)

    await read(['manufacturer', 'model'])
    if extra_info['manufacturer'] is None or extra_info['model'] is None:
        # Some devices fail at returning multiple results. Attempt separately.
        await read(['manufacturer'])
        await read(['model'])

    for key, value in extra_info.items():
        if isinstance(value, bytes):
            try:
                extra_info[key] = value.decode('ascii').strip()
            except UnicodeDecodeError:
                # Unsure what the best behaviour here is. Unset the key?
                pass

    return extra_info


def get_discovery_info(hass, discovery_info):
    """Get the full discovery info for a device.

    Some of the info that needs to be passed to platforms is not JSON
    serializable, so it cannot be put in the discovery_info dictionary. This
    component places that info we need to pass to the platform in hass.data,
    and this function is a helper for platforms to retrieve the complete
    discovery info.
    """
    if discovery_info is None:
        return

    discovery_key = discovery_info.get('discovery_key', None)
    all_discovery_info = hass.data.get(DISCOVERY_KEY, {})
    return all_discovery_info.get(discovery_key, None)


async def safe_read(cluster, attributes, allow_cache=True):
    """Swallow all exceptions from network read.

    If we throw during initialization, setup fails. Rather have an entity that
    exists, but is in a maybe wrong state, than no entity. This method should
    probably only be used during initialization.
    """
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=allow_cache,
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}

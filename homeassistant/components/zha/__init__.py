"""
Support for ZigBee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import const as ha_const
from homeassistant.helpers import discovery, entity
from homeassistant.util import slugify

REQUIREMENTS = ['bellows==0.2.7']

DOMAIN = 'zha'

CONF_USB_PATH = 'usb_path'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
DATA_DEVICE_CONFIG = 'zha_device_config'

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(ha_const.CONF_TYPE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        CONF_USB_PATH: cv.string,
        CONF_DATABASE: cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_DURATION = 'duration'

SERVICE_PERMIT = 'permit'
SERVICE_DESCRIPTIONS = {
    SERVICE_PERMIT: {
        "description": "Allow nodes to join the Zigbee network",
        "fields": {
            "duration": {
                "description": "Time to permit joins, in seconds",
                "example": "60",
            },
        },
    },
}
SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(1, 254)),
    }),
}


# ZigBee definitions
CENTICELSIUS = 'C-100'
# Key in hass.data dict containing discovery info
DISCOVERY_KEY = 'zha_discovery_info'

# Internal definitions
APPLICATION_CONTROLLER = None
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """
    global APPLICATION_CONTROLLER

    import bellows.ezsp
    from bellows.zigbee.application import ControllerApplication

    ezsp_ = bellows.ezsp.EZSP()
    usb_path = config[DOMAIN].get(CONF_USB_PATH)
    yield from ezsp_.connect(usb_path)

    database = config[DOMAIN].get(CONF_DATABASE)
    APPLICATION_CONTROLLER = ControllerApplication(ezsp_, database)
    listener = ApplicationListener(hass, config)
    APPLICATION_CONTROLLER.add_listener(listener)
    yield from APPLICATION_CONTROLLER.startup(auto_form=True)

    for device in APPLICATION_CONTROLLER.devices.values():
        hass.async_add_job(listener.async_device_initialized(device, False))

    @asyncio.coroutine
    def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        yield from APPLICATION_CONTROLLER.permit(duration)

    hass.services.async_register(DOMAIN, SERVICE_PERMIT, permit,
                                 SERVICE_DESCRIPTIONS[SERVICE_PERMIT],
                                 SERVICE_SCHEMAS[SERVICE_PERMIT])

    return True


class ApplicationListener:
    """All handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config
        hass.data[DISCOVERY_KEY] = hass.data.get(DISCOVERY_KEY, {})

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address
        """
        # Wait for device_initialized, instead
        pass

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self._hass.async_add_job(self.async_device_initialized(device, True))

    @asyncio.coroutine
    def async_device_initialized(self, device, join):
        """Handle device joined and basic information discovered (async)."""
        import bellows.zigbee.profiles
        import homeassistant.components.zha.const as zha_const
        zha_const.populate_data()

        for endpoint_id, endpoint in device.endpoints.items():
            if endpoint_id == 0:  # ZDO
                continue

            discovered_info = yield from _discover_endpoint_info(endpoint)

            component = None
            used_clusters = []
            device_key = '%s-%s' % (str(device.ieee), endpoint_id)
            node_config = self._config[DOMAIN][CONF_DEVICE_CONFIG].get(
                device_key, {})

            if endpoint.profile_id in bellows.zigbee.profiles.PROFILES:
                profile = bellows.zigbee.profiles.PROFILES[endpoint.profile_id]
                if zha_const.DEVICE_CLASS.get(endpoint.profile_id,
                                              {}).get(endpoint.device_type,
                                                      None):
                    used_clusters = profile.CLUSTERS[endpoint.device_type]
                    profile_info = zha_const.DEVICE_CLASS[endpoint.profile_id]
                    component = profile_info[endpoint.device_type]

            if ha_const.CONF_TYPE in node_config:
                component = node_config[ha_const.CONF_TYPE]
                used_clusters = zha_const.COMPONENT_CLUSTERS[component]

            if component:
                clusters = [endpoint.clusters[c] for c in used_clusters if c in
                            endpoint.clusters]
                discovery_info = {
                    'endpoint': endpoint,
                    'clusters': clusters,
                    'new_join': join,
                }
                discovery_info.update(discovered_info)
                self._hass.data[DISCOVERY_KEY][device_key] = discovery_info

                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    {'discovery_key': device_key},
                    self._config,
                )

            for cluster_id, cluster in endpoint.clusters.items():
                cluster_type = type(cluster)
                if cluster_id in used_clusters:
                    continue
                if cluster_type not in zha_const.SINGLE_CLUSTER_DEVICE_CLASS:
                    continue

                component = zha_const.SINGLE_CLUSTER_DEVICE_CLASS[cluster_type]
                discovery_info = {
                    'endpoint': endpoint,
                    'clusters': [cluster],
                    'new_join': join,
                }
                discovery_info.update(discovered_info)
                cluster_key = '%s-%s' % (device_key, cluster_id)
                self._hass.data[DISCOVERY_KEY][cluster_key] = discovery_info

                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    {'discovery_key': cluster_key},
                    self._config,
                )


class Entity(entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overriden by subclasses

    def __init__(self, endpoint, clusters, manufacturer, model, **kwargs):
        """Init ZHA entity."""
        self._device_state_attributes = {}
        ieeetail = ''.join([
            '%02x' % (o, ) for o in endpoint.device.ieee[-4:]
        ])
        if manufacturer and model is not None:
            self.entity_id = '%s.%s_%s_%s_%s' % (
                self._domain,
                slugify(manufacturer),
                slugify(model),
                ieeetail,
                endpoint.endpoint_id,
            )
            self._device_state_attributes['friendly_name'] = '%s %s' % (
                manufacturer,
                model,
            )
        else:
            self.entity_id = "%s.zha_%s_%s" % (
                self._domain,
                ieeetail,
                endpoint.endpoint_id,
            )
        for cluster in clusters:
            cluster.add_listener(self)
        self._endpoint = endpoint
        self._clusters = {c.cluster_id: c for c in clusters}
        self._state = ha_const.STATE_UNKNOWN

    def attribute_updated(self, attribute, value):
        """Handle an attribute updated on this cluster."""
        pass

    def zdo_command(self, aps_frame, tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        pass

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes


@asyncio.coroutine
def _discover_endpoint_info(endpoint):
    """Find some basic information about an endpoint."""
    extra_info = {
        'manufacturer': None,
        'model': None,
    }
    if 0 not in endpoint.clusters:
        return extra_info

    result, _ = yield from endpoint.clusters[0].read_attributes(
        ['manufacturer', 'model'],
        allow_cache=True,
    )
    extra_info.update(result)

    for key, value in extra_info.items():
        if isinstance(value, bytes):
            try:
                extra_info[key] = value.decode('ascii')
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
    discovery_info = all_discovery_info.get(discovery_key, None)
    return discovery_info

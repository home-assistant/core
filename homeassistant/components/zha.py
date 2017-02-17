"""
Support for ZigBee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant import const
from homeassistant.helpers import discovery, entity
from homeassistant.util import slugify
import homeassistant.helpers.config_validation as cv


# Definitions for interfacing with the rest of HA
REQUIREMENTS = ['bellows==0.2.2']

DOMAIN = 'zha'

CONF_USB_PATH = 'usb_path'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
DATA_DEVICE_CONFIG = 'zha_device_config'

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(const.CONF_TYPE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        CONF_USB_PATH: cv.string,
        CONF_DATABASE: cv.string,
        vol.Optional(CONF_DEVICE_CONFIG):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_DURATION = "duration"

SERVICE_PERMIT = "permit"
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

# Device types which require more than one cluster to work together
DEVICE_TYPES = {
    260: {  # ZHA
        0x0000: ('switch', [0x0004, 0x0005, 0x0006, 0x0007]),
        0x0100: ('light', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0101: ('light', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0102: ('light', [0x0004, 0x0005, 0x0006, 0x0008, 0x0300]),
    },
    49246: {  # ZLL
        0x0000: ('light', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0010: ('switch', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0100: ('light', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0110: ('switch', [0x0004, 0x0005, 0x0006, 0x0008]),
        0x0200: ('light', [0x0004, 0x0005, 0x0006, 0x0008, 0x0300]),
        0x0210: ('light', [0x0004, 0x0005, 0x0006, 0x0008, 0x0300]),
        0x0220: ('light', [0x0004, 0x0005, 0x0006, 0x0008, 0x0300]),
    }, 64513: {  # Probably SmartThings. Maybe.
        # This shouldn't be in here, but rather in some sort of quirks database
        0x019a: ('device_tracker', []),
    }
}

CLUSTERS = {
    0x0006: ('switch', 0x0000, {}),
    0x0402: ('sensor', 0x0000, {'unit_of_measurement': CENTICELSIUS}),
    0x0500: ('binary_sensor', 0x0002, {}),
}


# Internal definitions
APPLICATION_CONTROLLER = None
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup ZHA.

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
    """Handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config

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
        for endpoint_id, endpoint in device.endpoints.items():
            if endpoint_id == 0:  # ZDO
                continue

            discovered_info = yield from _discover_endpoint_info(endpoint)

            used_clusters = []
            device_key = '%s-%s' % (str(device.ieee), endpoint_id)
            node_config = self._config[DOMAIN][CONF_DEVICE_CONFIG].get(
                device_key, {})
            if DEVICE_TYPES.get(endpoint.profile_id,
                                {}).get(endpoint.device_type, None):
                # This device has a bunch of predefined clusters which work
                # together as one device.
                profile_types = DEVICE_TYPES[endpoint.profile_id]
                component, used_clusters = profile_types[endpoint.device_type]
                if const.CONF_TYPE in node_config:
                    component = node_config[const.CONF_TYPE]
                clusters = [endpoint.clusters[c]
                            for c in used_clusters
                            if c in endpoint.clusters]
                discovery_info = {
                    'endpoint': endpoint,
                    'clusters': clusters,
                    'new_join': join,
                }
                discovery_info.update(discovered_info)
                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    discovery_info,
                    self._config,
                )

            for cluster_id, cluster in endpoint.clusters.items():
                if cluster_id not in CLUSTERS or cluster_id in used_clusters:
                    continue

                component, value_attribute, extra_info = CLUSTERS[cluster_id]
                discovery_info = {
                    'endpoint': endpoint,
                    'clusters': [cluster],
                    'value_attribute': value_attribute,
                    'new_join': join,
                }
                discovery_info.update(extra_info)
                discovery_info.update(discovered_info)

                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    discovery_info,
                    self._config,
                )


class Entity(entity.Entity):
    """A base class for ZHA entities."""

    _domain = None  # Must be overriden by subclasses

    def __init__(self, endpoint, clusters, manufacturer, model, **kwargs):
        """Initialize ZHA entity."""
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
        self._state = const.STATE_UNKNOWN

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

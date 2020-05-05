"""Support the ISY-994 controllers."""
from collections import namedtuple
from urllib.parse import urlparse

import PyISY
from PyISY.Nodes import Group
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.fan import DOMAIN as FAN
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, Dict

from .const import (
    _LOGGER,
    CONF_ENABLE_CLIMATE,
    CONF_IGNORE_STRING,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    DEFAULT_IGNORE_STRING,
    DEFAULT_SENSOR_STRING,
    DOMAIN,
    ISY994_NODES,
    ISY994_PROGRAMS,
    ISY994_WEATHER,
    ISY_GROUP_PLATFORM,
    KEY_ACTIONS,
    KEY_FOLDER,
    KEY_MY_PROGRAMS,
    KEY_STATUS,
    NODE_FILTERS,
    SUPPORTED_PLATFORMS,
    SUPPORTED_PROGRAM_PLATFORMS,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.url,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TLS_VER): vol.Coerce(float),
                vol.Optional(
                    CONF_IGNORE_STRING, default=DEFAULT_IGNORE_STRING
                ): cv.string,
                vol.Optional(
                    CONF_SENSOR_STRING, default=DEFAULT_SENSOR_STRING
                ): cv.string,
                vol.Optional(CONF_ENABLE_CLIMATE, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

WeatherNode = namedtuple("WeatherNode", ("status", "name", "uom"))


def _check_for_node_def(hass: HomeAssistant, node, single_platform: str = None) -> bool:
    """Check if the node matches the node_def_id for any platforms.

    This is only present on the 5.0 ISY firmware, and is the most reliable
    way to determine a device's type.
    """
    if not hasattr(node, "node_def_id") or node.node_def_id is None:
        # Node doesn't have a node_def (pre 5.0 firmware most likely)
        return False

    node_def_id = node.node_def_id

    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if node_def_id in NODE_FILTERS[platform]["node_def_id"]:
            hass.data[ISY994_NODES][platform].append(node)
            return True

    _LOGGER.warning("Unsupported node: %s, type: %s", node.name, node.type)
    return False


def _check_for_insteon_type(
    hass: HomeAssistant, node, single_platform: str = None
) -> bool:
    """Check if the node matches the Insteon type for any platforms.

    This is for (presumably) every version of the ISY firmware, but only
    works for Insteon device. "Node Server" (v5+) and Z-Wave and others will
    not have a type.
    """
    if not hasattr(node, "type") or node.type is None:
        # Node doesn't have a type (non-Insteon device most likely)
        return False

    device_type = node.type
    platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
    for platform in platforms:
        if any(
            [
                device_type.startswith(t)
                for t in set(NODE_FILTERS[platform]["insteon_type"])
            ]
        ):

            # Hacky special-case just for FanLinc, which has a light module
            # as one of its nodes. Note that this special-case is not necessary
            # on ISY 5.x firmware as it uses the superior NodeDefs method
            if platform == FAN and int(node.nid[-1]) == 1:
                hass.data[ISY994_NODES][LIGHT].append(node)
                return True

            hass.data[ISY994_NODES][platform].append(node)
            return True

    return False


def _check_for_uom_id(
    hass: HomeAssistant, node, single_platform: str = None, uom_list: list = None
) -> bool:
    """Check if a node's uom matches any of the platforms uom filter.

    This is used for versions of the ISY firmware that report uoms as a single
    ID. We can often infer what type of device it is by that ID.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if uom_list:
        if node_uom.intersection(uom_list):
            hass.data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom.intersection(NODE_FILTERS[platform]["uom"]):
                hass.data[ISY994_NODES][platform].append(node)
                return True

    return False


def _check_for_states_in_uom(
    hass: HomeAssistant, node, single_platform: str = None, states_list: list = None
) -> bool:
    """Check if a list of uoms matches two possible filters.

    This is for versions of the ISY firmware that report uoms as a list of all
    possible "human readable" states. This filter passes if all of the possible
    states fit inside the given filter.
    """
    if not hasattr(node, "uom") or node.uom is None:
        # Node doesn't have a uom (Scenes for example)
        return False

    node_uom = set(map(str.lower, node.uom))

    if states_list:
        if node_uom == set(states_list):
            hass.data[ISY994_NODES][single_platform].append(node)
            return True
    else:
        platforms = SUPPORTED_PLATFORMS if not single_platform else [single_platform]
        for platform in platforms:
            if node_uom == set(NODE_FILTERS[platform]["states"]):
                hass.data[ISY994_NODES][platform].append(node)
                return True

    return False


def _is_sensor_a_binary_sensor(hass: HomeAssistant, node) -> bool:
    """Determine if the given sensor node should be a binary_sensor."""
    if _check_for_node_def(hass, node, single_platform=BINARY_SENSOR):
        return True
    if _check_for_insteon_type(hass, node, single_platform=BINARY_SENSOR):
        return True

    # For the next two checks, we're providing our own set of uoms that
    # represent on/off devices. This is because we can only depend on these
    # checks in the context of already knowing that this is definitely a
    # sensor device.
    if _check_for_uom_id(
        hass, node, single_platform=BINARY_SENSOR, uom_list=["2", "78"]
    ):
        return True
    if _check_for_states_in_uom(
        hass, node, single_platform=BINARY_SENSOR, states_list=["on", "off"]
    ):
        return True

    return False


def _categorize_nodes(
    hass: HomeAssistant, nodes, ignore_identifier: str, sensor_identifier: str
) -> None:
    """Sort the nodes to their proper platforms."""
    for (path, node) in nodes:
        ignored = ignore_identifier in path or ignore_identifier in node.name
        if ignored:
            # Don't import this node as a device at all
            continue

        if isinstance(node, Group):
            hass.data[ISY994_NODES][ISY_GROUP_PLATFORM].append(node)
            continue

        if sensor_identifier in path or sensor_identifier in node.name:
            # User has specified to treat this as a sensor. First we need to
            # determine if it should be a binary_sensor.
            if _is_sensor_a_binary_sensor(hass, node):
                continue

            hass.data[ISY994_NODES][SENSOR].append(node)
            continue

        # We have a bunch of different methods for determining the device type,
        # each of which works with different ISY firmware versions or device
        # family. The order here is important, from most reliable to least.
        if _check_for_node_def(hass, node):
            continue
        if _check_for_insteon_type(hass, node):
            continue
        if _check_for_uom_id(hass, node):
            continue
        if _check_for_states_in_uom(hass, node):
            continue


def _categorize_programs(hass: HomeAssistant, programs: dict) -> None:
    """Categorize the ISY994 programs."""
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        try:
            folder = programs[KEY_MY_PROGRAMS][f"HA.{platform}"]
        except KeyError:
            pass
        else:
            for dtype, _, node_id in folder.children:
                if dtype != KEY_FOLDER:
                    continue
                entity_folder = folder[node_id]
                try:
                    status = entity_folder[KEY_STATUS]
                    assert status.dtype == "program", "Not a program"
                    if platform != BINARY_SENSOR:
                        actions = entity_folder[KEY_ACTIONS]
                        assert actions.dtype == "program", "Not a program"
                    else:
                        actions = None
                except (AttributeError, KeyError, AssertionError):
                    _LOGGER.warning(
                        "Program entity '%s' not loaded due "
                        "to invalid folder structure.",
                        entity_folder.name,
                    )
                    continue

                entity = (entity_folder.name, status, actions)
                hass.data[ISY994_PROGRAMS][platform].append(entity)


def _categorize_weather(hass: HomeAssistant, climate) -> None:
    """Categorize the ISY994 weather data."""
    climate_attrs = dir(climate)
    weather_nodes = [
        WeatherNode(
            getattr(climate, attr),
            attr.replace("_", " "),
            getattr(climate, f"{attr}_units"),
        )
        for attr in climate_attrs
        if f"{attr}_units" in climate_attrs
    ]
    hass.data[ISY994_WEATHER].extend(weather_nodes)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ISY 994 platform."""
    hass.data[ISY994_NODES] = {}
    for platform in SUPPORTED_PLATFORMS:
        hass.data[ISY994_NODES][platform] = []

    hass.data[ISY994_WEATHER] = []

    hass.data[ISY994_PROGRAMS] = {}
    for platform in SUPPORTED_PROGRAM_PLATFORMS:
        hass.data[ISY994_PROGRAMS][platform] = []

    isy_config = config.get(DOMAIN)

    user = isy_config.get(CONF_USERNAME)
    password = isy_config.get(CONF_PASSWORD)
    tls_version = isy_config.get(CONF_TLS_VER)
    host = urlparse(isy_config.get(CONF_HOST))
    ignore_identifier = isy_config.get(CONF_IGNORE_STRING)
    sensor_identifier = isy_config.get(CONF_SENSOR_STRING)
    enable_climate = isy_config.get(CONF_ENABLE_CLIMATE)

    if host.scheme == "http":
        https = False
        port = host.port or 80
    elif host.scheme == "https":
        https = True
        port = host.port or 443
    else:
        _LOGGER.error("isy994 host value in configuration is invalid")
        return False

    # Connect to ISY controller.
    isy = PyISY.ISY(
        host.hostname,
        port,
        username=user,
        password=password,
        use_https=https,
        tls_ver=tls_version,
        log=_LOGGER,
    )
    if not isy.connected:
        return False

    _categorize_nodes(hass, isy.nodes, ignore_identifier, sensor_identifier)
    _categorize_programs(hass, isy.programs)

    if enable_climate and isy.configuration.get("Weather Information"):
        _categorize_weather(hass, isy.climate)

    def stop(event: object) -> None:
        """Stop ISY auto updates."""
        isy.auto_update = False

    # Listen for HA stop to disconnect.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    # Load platforms for the devices in the ISY controller that we support.
    for platform in SUPPORTED_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    isy.auto_update = True
    return True


class ISYDevice(Entity):
    """Representation of an ISY994 device."""

    _attrs = {}
    _name: str = None

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._change_handler = None
        self._control_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status.subscribe("changed", self.on_update)

        if hasattr(self._node, "controlEvents"):
            self._control_handler = self._node.controlEvents.subscribe(self.on_control)

    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    def on_control(self, event: object) -> None:
        """Handle a control event from the ISY994 Node."""
        self.hass.bus.fire(
            "isy994_control", {"entity_id": self.entity_id, "control": event}
        )

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        # pylint: disable=protected-access
        if hasattr(self._node, "_id"):
            return self._node._id

        return None

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._name or str(self._node.name)

    @property
    def should_poll(self) -> bool:
        """No polling required since we're using the subscription."""
        return False

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        # pylint: disable=protected-access
        return self._node.status._val

    def is_unknown(self) -> bool:
        """Get whether or not the value of this Entity's node is unknown.

        PyISY reports unknown values as -inf
        """
        return self.value == -1 * float("inf")

    @property
    def state(self):
        """Return the state of the ISY device."""
        if self.is_unknown():
            return None
        return super().state

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        if hasattr(self._node, "aux_properties"):
            for name, val in self._node.aux_properties.items():
                attr[name] = f"{val.get('value')} {val.get('uom')}"
        return attr

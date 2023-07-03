"""Handle manual setup of ihc resources as entities in Home Assistant."""
import logging
import os.path

import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.config import load_yaml_config_file
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BINARY_SENSOR,
    CONF_DIMMABLE,
    CONF_INVERTING,
    CONF_LIGHT,
    CONF_NOTE,
    CONF_OFF_ID,
    CONF_ON_ID,
    CONF_POSITION,
    CONF_SENSOR,
    CONF_SWITCH,
    DOMAIN,
    IHC_PLATFORMS,
    MANUAL_SETUP_YAML,
)

_LOGGER = logging.getLogger(__name__)


def validate_name(config):
    """Validate the device name."""
    if CONF_NAME in config:
        return config
    ihcid = config[CONF_ID]
    name = f"ihc_{ihcid}"
    config[CONF_NAME] = name
    return config


DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_NOTE): cv.string,
        vol.Optional(CONF_POSITION): cv.string,
    }
)

SWITCH_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        vol.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

BINARY_SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_INVERTING, default=False): cv.boolean,
        vol.Optional(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
    }
)

LIGHT_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
        vol.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        vol.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string}
)


MANUAL_SETUP_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Required("controller"): cv.string,
                            vol.Optional(CONF_BINARY_SENSOR, default=[]): vol.All(
                                cv.ensure_list,
                                [vol.All(BINARY_SENSOR_SCHEMA, validate_name)],
                            ),
                            vol.Optional(CONF_LIGHT, default=[]): vol.All(
                                cv.ensure_list, [vol.All(LIGHT_SCHEMA, validate_name)]
                            ),
                            vol.Optional(CONF_SENSOR, default=[]): vol.All(
                                cv.ensure_list, [vol.All(SENSOR_SCHEMA, validate_name)]
                            ),
                            vol.Optional(CONF_SWITCH, default=[]): vol.All(
                                cv.ensure_list, [vol.All(SWITCH_SCHEMA, validate_name)]
                            ),
                        }
                    )
                ],
            )
        )
    }
)


def manual_setup(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Manual setup of IHC devices."""
    yaml_path = hass.config.path(MANUAL_SETUP_YAML)
    if not os.path.isfile(yaml_path):
        return
    yaml = load_yaml_config_file(yaml_path)
    try:
        ihc_conf = MANUAL_SETUP_SCHEMA(yaml)[DOMAIN]
    except vol.Invalid as exception:
        _LOGGER.error("Invalid IHC manual setup data: %s", exception)
        return
    assert entry.unique_id is not None
    controller_id: str = entry.unique_id
    # Find the controller config for this controller
    controller_conf = None
    for conf in ihc_conf:
        if conf["controller"] == controller_id:
            controller_conf = conf
            break
    if controller_conf is None:
        return
    # Get manual configuration for IHC devices
    for platform in IHC_PLATFORMS:
        discovery_info = {}
        if platform in controller_conf:
            platform_setup = controller_conf.get(platform, {})
            for sensor_cfg in platform_setup:
                name = sensor_cfg[CONF_NAME]
                device = {
                    "ihc_id": sensor_cfg[CONF_ID],
                    "ctrl_id": controller_id,
                    "product": {
                        "name": name,
                        "note": sensor_cfg.get(CONF_NOTE) or "",
                        "position": sensor_cfg.get(CONF_POSITION) or "",
                    },
                    "product_cfg": {
                        "type": sensor_cfg.get(CONF_TYPE),
                        "inverting": sensor_cfg.get(CONF_INVERTING),
                        "off_id": sensor_cfg.get(CONF_OFF_ID),
                        "on_id": sensor_cfg.get(CONF_ON_ID),
                        "dimmable": sensor_cfg.get(CONF_DIMMABLE),
                        "unit_of_measurement": sensor_cfg.get(CONF_UNIT_OF_MEASUREMENT),
                    },
                }
                discovery_info[name] = device
        if discovery_info:
            if platform in hass.data[DOMAIN][entry.entry_id]:
                hass.data[DOMAIN][entry.entry_id][platform].update(discovery_info)
            else:
                hass.data[DOMAIN][entry.entry_id][platform] = discovery_info

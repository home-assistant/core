"""
homeassistant.components.scene
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scenes are a sequence of actions that can be triggered manually
by the user or automatically based upon automation events, etc.
"""
import logging
from datetime import datetime, timedelta

from homeassistant.util import split_entity_id

DOMAIN = "scene"
DEPENDENCIES = ["group"]

SERVICE_RUN = "run"
CONF_ALIAS = "alias"
CONF_SCENE_NAME = "scene_name"
CONF_SERVICE = "execute_service"
CONF_SERVICE_DATA = "service_data"
CONF_SEQUENCE = "sequence"
CONF_DELAY = "delay"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Load the scenes from the configuration. """

    scenes = {}
    for name, cfg in config.get(DOMAIN, {}).items():
        scene = create_scene(name, cfg)
        if scene:
            _LOGGER.info("Registered scene %s", name)
            scenes[name] = scene

    def handle_scene_service(service):
        """ Handle a scene service call. """
        data = service.data
        name = data.get(CONF_SCENE_NAME)
        if name in scenes:
            scenes[name](hass)
        else:
            _LOGGER.warn("Unknown scene: %s", name)

    hass.services.register(DOMAIN, SERVICE_RUN, handle_scene_service)

    return True


def create_scene(scene_name, config):
    """ Returns a scene. """

    if not CONF_SEQUENCE in config:
        _LOGGER.warn("Missing key 'sequence' for scene %s", scene_name)
        return

    def run_scene(hass):
        """ Executes a sequence of actions for a scene. """
        _LOGGER.info("Executing scene %s", config.get(CONF_ALIAS, scene_name))
        point_in_time = datetime.now()
        for action in config[CONF_SEQUENCE]:
            if CONF_SERVICE in action:
                call_service(hass, scene_name, action, point_in_time)
            elif CONF_DELAY in action:
                point_in_time += timedelta(**action[CONF_DELAY])

    return run_scene


def call_service(hass, scene_name, config, point_in_time):
    """ Calls a service at some point in time. """
    domain, service = split_entity_id(config[CONF_SERVICE])
    data = config.get(CONF_SERVICE_DATA, {})

    def call(now):
        """ Actually calls the service. """
        _LOGGER.info("Executing scene %s step %s", scene_name,
                     config.get(CONF_ALIAS, ""))
        hass.services.call(domain, service, data)

    hass.track_point_in_time(call, point_in_time)

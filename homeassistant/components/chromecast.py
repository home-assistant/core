"""
homeassistant.components.chromecast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with Chromecasts.
"""
import logging

import homeassistant as ha
import homeassistant.util as util
import homeassistant.components as components

DOMAIN = 'chromecast'

SERVICE_YOUTUBE_VIDEO = 'play_youtube_video'

ENTITY_ID_FORMAT = DOMAIN + '.{}'
STATE_NO_APP = 'no_app'

ATTR_FRIENDLY_NAME = 'friendly_name'
ATTR_HOST = 'host'
ATTR_STATE = 'state'
ATTR_OPTIONS = 'options'


def is_on(statemachine, entity_id=None):
    """ Returns true if specified ChromeCast entity_id is on.
    Will check all chromecasts if no entity_id specified. """

    entity_ids = [entity_id] if entity_id \
        else util.filter_entity_ids(statemachine.entity_ids, DOMAIN)

    return any(not statemachine.is_state(entity_id, STATE_NO_APP)
               for entity_id in entity_ids)


def setup(bus, statemachine, host):
    """ Listen for chromecast events. """
    logger = logging.getLogger(__name__)

    try:
        from homeassistant.external import pychromecast
    except ImportError:
        logger.exception(("Failed to import pychromecast. "
                          "Did you maybe not cloned the git submodules?"))

        return False

    logger.info("Getting device status")
    device = pychromecast.get_device_status(host)

    if not device:
        logger.error("Could not find Chromecast")
        return False

    entity = ENTITY_ID_FORMAT.format(util.slugify(device.friendly_name))

    if not bus.has_service(DOMAIN, components.SERVICE_TURN_OFF):
        def turn_off_service(service):
            """ Service to exit any running app on the specified ChromeCast and
            shows idle screen. Will quit all ChromeCasts if nothing specified.
            """
            entity_id = service.data.get(components.ATTR_ENTITY_ID)

            entity_ids = [entity_id] if entity_id \
                else util.filter_entity_ids(statemachine.entity_ids, DOMAIN)

            for entity_id in entity_ids:
                state = statemachine.get_state(entity_id)

                try:
                    pychromecast.quit_app(state.attributes[ATTR_HOST])
                except (AttributeError, KeyError):
                    # AttributeError: state returned None
                    # KeyError: ATTR_HOST did not exist
                    pass

        bus.register_service(DOMAIN, components.SERVICE_TURN_OFF,
                             turn_off_service)

    bus.register_service(DOMAIN, "start_fireplace",
                         lambda service:
                         pychromecast.play_youtube_video(host, "eyU3bRy2x44"))

    bus.register_service(DOMAIN, "start_epic_sax",
                         lambda service:
                         pychromecast.play_youtube_video(host, "kxopViU98Xo"))

    bus.register_service(DOMAIN, SERVICE_YOUTUBE_VIDEO,
                         lambda service:
                         pychromecast.play_youtube_video(
                             host, service.data['video']))

    def update_chromecast_state(time):  # pylint: disable=unused-argument
        """ Retrieve state of Chromecast and update statemachine. """
        logger.info("Updating app status")
        status = pychromecast.get_app_status(host)

        if status:
            state = STATE_NO_APP if status.name == pychromecast.APP_ID_HOME \
                else status.name
            statemachine.set_state(entity, state,
                                   {ATTR_FRIENDLY_NAME:
                                       pychromecast.get_friendly_name(
                                           status.name),
                                    ATTR_HOST: host,
                                    ATTR_STATE: status.state,
                                    ATTR_OPTIONS: status.options})
        else:
            statemachine.set_state(entity, STATE_NO_APP, {ATTR_HOST: host})

    ha.track_time_change(bus, update_chromecast_state)

    update_chromecast_state(None)

    return True

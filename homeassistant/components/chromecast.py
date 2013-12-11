"""
homeassistant.components.chromecast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with Chromecasts.
"""

from homeassistant.packages import pychromecast

import homeassistant as ha
import homeassistant.util as util


DOMAIN_CHROMECAST = "chromecast"

SERVICE_YOUTUBE_VIDEO = "play_youtube_video"

STATE_CATEGORY_FORMAT = 'chromecasts.{}'
STATE_NO_APP = "none"

ATTR_FRIENDLY_NAME = "friendly_name"
ATTR_HOST = "host"
ATTR_STATE = "state"
ATTR_OPTIONS = "options"


def get_ids(statemachine):
    """ Gets the IDs of the different Chromecasts that are being tracked. """
    return ha.get_grouped_state_cats(statemachine, STATE_CATEGORY_FORMAT, True)


def get_categories(statemachine):
    """ Gets the categories of the different Chromecasts that are being
    tracked. """
    return ha.get_grouped_state_cats(statemachine, STATE_CATEGORY_FORMAT,
                                     False)


def turn_off(statemachine, cc_id=None):
    """ Exits any running app on the specified ChromeCast and shows
    idle screen. Will quit all ChromeCasts if nothing specified. """

    cats = [STATE_CATEGORY_FORMAT.format(cc_id)] if cc_id \
        else get_categories(statemachine)

    for cat in cats:
        state = statemachine.get_state(cat)

        if state and \
           state['state'] != STATE_NO_APP or \
           state['state'] != pychromecast.APP_ID_HOME:

            pychromecast.quit_app(state['attributes'][ATTR_HOST])


def setup(bus, statemachine, host):
    """ Listen for chromecast events. """
    device = pychromecast.get_device_status(host)

    if not device:
        return False

    category = STATE_CATEGORY_FORMAT.format(util.slugify(
        device.friendly_name))

    bus.register_service(DOMAIN_CHROMECAST, ha.SERVICE_TURN_OFF,
                         lambda service:
                         turn_off(statemachine,
                                  service.data.get("cc_id", None)))

    bus.register_service(DOMAIN_CHROMECAST, "start_fireplace",
                         lambda service:
                         pychromecast.play_youtube_video(host, "eyU3bRy2x44"))

    bus.register_service(DOMAIN_CHROMECAST, "start_epic_sax",
                         lambda service:
                         pychromecast.play_youtube_video(host, "kxopViU98Xo"))

    bus.register_service(DOMAIN_CHROMECAST, SERVICE_YOUTUBE_VIDEO,
                         lambda service:
                         pychromecast.play_youtube_video(
                             host, service.data['video']))

    def update_chromecast_state(time):  # pylint: disable=unused-argument
        """ Retrieve state of Chromecast and update statemachine. """
        status = pychromecast.get_app_status(host)

        if status:
            statemachine.set_state(category, status.name,
                                   {ATTR_FRIENDLY_NAME:
                                       pychromecast.get_friendly_name(
                                           status.name),
                                    ATTR_HOST: host,
                                    ATTR_STATE: status.state,
                                    ATTR_OPTIONS: status.options})
        else:
            statemachine.set_state(category, STATE_NO_APP)

    ha.track_time_change(bus, update_chromecast_state)

    update_chromecast_state(None)

    return True

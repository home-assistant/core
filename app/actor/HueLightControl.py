from phue import Bridge

MAX_TRANSITION_TIME = 9000


def process_transition_time(transition_seconds):
    """ Transition time is in 1/10th seconds and cannot exceed MAX_TRANSITION_TIME. """
    return min(MAX_TRANSITION_TIME, transition_seconds * 10)


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, config=None):
        self.bridge = Bridge(config.get("hue","host") if config is not None and config.has_option("hue","host") else None)
        self.lights = self.bridge.get_light_objects()
        self.light_ids = [light.light_id for light in self.lights]


    def is_light_on(self, light_id=None):
        """ Returns if specified light is on.

            If light_id not specified will report on combined status of all lights. """
        if light_id is None:
            return sum([1 for light in self.lights if light.on]) > 0

        else:
            return self.bridge.get_light(light_id, 'on')


    def turn_light_on(self, light_id=None, transition_seconds=None):
        if light_id is None:
            light_id = self.light_ids

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri':164}

        if transition_seconds is not None:
            command['transitiontime'] = process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)


    def turn_light_off(self, light_id=None, transition_seconds=None):
        if light_id is None:
            light_id = self.light_ids

        command = {'on': False}

        if transition_seconds is not None:
            command['transitiontime'] = process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)

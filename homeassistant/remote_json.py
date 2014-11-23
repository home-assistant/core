# pylint: skip-file
"""
Helper methods for using JSON.

This used to be in homeassistant.remote but has been moved
to this module because of a bug in PyLint that would make it crash.
"""
import homeassistant as ha
import json


class JSONEncoder(json.JSONEncoder):
    """ JSONEncoder that supports Home Assistant objects. """

    def default(self, obj):
        """ Checks if Home Assistat object and encodes if possible.
        Else hand it off to original method. """
        if isinstance(obj, ha.State):
            return obj.as_dict()

        return json.JSONEncoder.default(self, obj)

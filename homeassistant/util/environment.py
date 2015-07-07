""" Environement helpers. """
import sys


def is_virtual():
    """ Return if we run in a virtual environtment. """
    return sys.base_prefix != sys.prefix

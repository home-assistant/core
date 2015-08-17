"""
homeassistant.util.temperature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Temperature util functions.
"""


def f_to_c(fahrenheit):
    """ Convert a Fahrenheit temperature to Celcius. """
    return (fahrenheit - 32.0) / 1.8


def c_to_f(celcius):
    """ Convert a Celcius temperature to Fahrenheit. """
    return celcius * 1.8 + 32.0

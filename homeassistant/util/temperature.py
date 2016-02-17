"""
homeassistant.util.temperature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Temperature util functions.
"""


def fahrenheit_to_celcius(fahrenheit):
    """ Convert a Fahrenheit temperature to Celcius. """
    return (fahrenheit - 32.0) / 1.8


def celcius_to_fahrenheit(celcius):
    """ Convert a Celcius temperature to Fahrenheit. """
    return celcius * 1.8 + 32.0

"""Temperature util functions."""

import logging


def fahrenheit_to_celcius(fahrenheit):
    """**DEPRECATED** Convert a Fahrenheit temperature to Celsius."""
    logging.getLogger(__name__).warning(
        'fahrenheit_to_celcius is now fahrenheit_to_celsius '
        'correcting a spelling mistake')
    return fahrenheit_to_celsius(fahrenheit)


def fahrenheit_to_celsius(fahrenheit):
    """Convert a Fahrenheit temperature to Celsius."""
    return (fahrenheit - 32.0) / 1.8


def celcius_to_fahrenheit(celcius):
    """**DEPRECATED** Convert a Celsius temperature to Fahrenheit."""
    logging.getLogger(__name__).warning(
        'celcius_to_fahrenheit is now celsius_to_fahrenheit correcting '
        'a spelling mistake')
    return celsius_to_fahrenheit(celcius)


def celsius_to_fahrenheit(celsius):
    """Convert a Celsius temperature to Fahrenheit."""
    return celsius * 1.8 + 32.0

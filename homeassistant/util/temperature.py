"""Temperature util functions."""


def fahrenheit_to_celcius(fahrenheit):
    """Convert a Fahrenheit temperature to Celsius."""
    return (fahrenheit - 32.0) / 1.8


def celcius_to_fahrenheit(celcius):
    """Convert a Celsius temperature to Fahrenheit."""
    return celcius * 1.8 + 32.0

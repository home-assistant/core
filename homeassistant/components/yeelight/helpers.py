"""Helpers for the Yeelight integration."""

import yeelight

from homeassistant.core import callback


@callback
def transitions_config_parser(transitions):
    """Parse transitions config into initialized objects."""
    transition_objects = []
    for transition_config in transitions:
        transition, params = list(transition_config.items())[0]
        transition_objects.append(getattr(yeelight, transition)(*params))

    return transition_objects

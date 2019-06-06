"""Helpers for amcrest component."""
from .const import DOMAIN


def service_signal(service, entity_id=None):
    """Encode service and entity_id into signal."""
    signal = '{}_{}'.format(DOMAIN, service)
    if entity_id:
        signal += '_{}'.format(entity_id.replace('.', '_'))
    return signal

"""
Deprecated since 3/21/2015 - please use helpers.entity_component
"""
import logging

# pylint: disable=unused-import
from .entity_component import EntityComponent as DeviceComponent  # noqa

logging.getLogger(__name__).warning(
    'This file is deprecated. Please use helpers.entity_component')

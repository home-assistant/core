"""
Deprecated since 3/21/2015 - please use helpers.entity
"""
import logging

# pylint: disable=unused-import
from .entity import Entity as Device, ToggleEntity as ToggleDevice  # noqa

logging.getLogger(__name__).warning(
    'This file is deprecated. Please use helpers.entity')

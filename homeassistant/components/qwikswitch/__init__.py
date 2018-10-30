"""
Support for Qwikswitch devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/qwikswitch/
"""
# pylint: disable=unused-import
from .qs import DOMAIN, QSEntity, QSToggleEntity  # noqa
from .qsusb import async_setup, CONFIG_SCHEMA  # noqa
from .qscloud import async_setup_entry, async_unload_entry  # noqa

REQUIREMENTS = ['pyqwikswitch==0.8']

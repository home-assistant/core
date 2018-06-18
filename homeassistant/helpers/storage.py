"""Helper to help store data."""
import logging
import os
from typing import Dict, Optional

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.loader import bind_hass
from homeassistant.util import json
from homeassistant.helpers.event import async_call_later

STORAGE_DIR = '.storage'
_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_migrator(hass, old_path, store, *, migrate_func=None):
    """Helper function to migrate old configs to a store and return config."""
    def load_old_config():
        """Helper to load old config."""
        if not os.path.isfile(old_path):
            return None

        return json.load_json(old_path)

    config = await hass.async_add_executor_job(load_old_config)

    if config is None:
        return await store.async_load()

    if migrate_func is not None:
        config = migrate_func(config)

    await store.async_save(config)
    await hass.async_add_executor_job(os.remove, old_path)
    return config


@bind_hass
class Store:
    """Class to help storing data."""

    def __init__(self, hass, key: str):
        """Initialize storage class."""
        self.hass = hass
        self.key = key
        self.path = hass.config.path(STORAGE_DIR, key)
        self._data = None
        self._unsub_delay_listener = None
        self._unsub_stop_listener = None

    async def async_load(self):
        """Load data."""
        if self._data is not None:
            return self._data

        return await self.hass.async_add_executor_job(
            json.load_json, self.path)

    async def async_save(self, data: Dict, *, delay: Optional[int] = None):
        """Save data with an optional delay."""
        self._data = data

        if delay is None:
            await self._handle_write_data()
            return

        if self._unsub_delay_listener is not None:
            self._unsub_delay_listener()
            self._unsub_delay_listener = None

        self._unsub_delay_listener = async_call_later(
            self.hass, delay, self._handle_write_data)

        # Ensure that we write if we quit before delay has passed.
        if self._unsub_stop_listener is None:
            self._unsub_stop_listener = self.hass.bus.async_listen(
                EVENT_HOMEASSISTANT_STOP, self._handle_write_data)

    async def _handle_write_data(self, *_args):
        """Handler to handle writing the config."""
        if self._unsub_delay_listener is not None:
            self._unsub_delay_listener()
            self._unsub_delay_listener = None

        if self._unsub_stop_listener is not None:
            self._unsub_stop_listener()
            self._unsub_stop_listener = None

        data = self._data
        self._data = None

        try:
            await self.hass.async_add_executor_job(
                self._write_data, self.path, data)
        except json.SerializationError as err:
            _LOGGER.error('Error writing config for %s: %s', self.key, err)
        except json.WriteError as err:
            _LOGGER.error('Error writing config for %s: %s', self.key, err)

    def _write_data(self, path: str, data: Dict):
        """Write the data."""
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        _LOGGER.debug('Writing data for %s', self.key)
        json.save_json(path, data)

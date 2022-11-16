"""Config flow for ZHA."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import Any

from zigpy.application import ControllerApplication
import zigpy.backups
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkNotFormed

from homeassistant.core import HomeAssistant

from .core.const import (
    CONF_DATABASE,
    CONF_ZIGPY,
    DATA_ZHA,
    DATA_ZHA_CONFIG,
    DEFAULT_DATABASE_NAME,
    RadioType,
)

# Only the common radio types will be autoprobed, ordered by new device popularity.
# XBee takes too long to probe since it scans through all possible bauds and likely has
# very few users to begin with.
AUTOPROBE_RADIOS = (
    RadioType.ezsp,
    RadioType.znp,
    RadioType.deconz,
    RadioType.zigate,
)

CONNECT_DELAY_S = 1.0

_LOGGER = logging.getLogger(__name__)


class ZhaRadioManager:
    """Helper class with radio related functionality."""

    hass: HomeAssistant

    def __init__(self) -> None:
        """Initialize ZhaRadioManager instance."""
        self.device_path: str | None = None
        self.device_settings: dict[str, Any] | None = None
        self.radio_type: RadioType | None = None
        self.current_settings: zigpy.backups.NetworkBackup | None = None
        self.backups: list[zigpy.backups.NetworkBackup] = []
        self.chosen_backup: zigpy.backups.NetworkBackup | None = None

    @contextlib.asynccontextmanager
    async def _connect_zigpy_app(self) -> ControllerApplication:
        """Connect to the radio with the current config and then clean up."""
        assert self.radio_type is not None

        config = self.hass.data.get(DATA_ZHA, {}).get(DATA_ZHA_CONFIG, {})
        app_config = config.get(CONF_ZIGPY, {}).copy()

        database_path = config.get(
            CONF_DATABASE,
            self.hass.config.path(DEFAULT_DATABASE_NAME),
        )

        # Don't create `zigbee.db` if it doesn't already exist
        if not await self.hass.async_add_executor_job(os.path.exists, database_path):
            database_path = None

        app_config[CONF_DATABASE] = database_path
        app_config[CONF_DEVICE] = self.device_settings
        app_config = self.radio_type.controller.SCHEMA(app_config)

        app = await self.radio_type.controller.new(
            app_config, auto_form=False, start_radio=False
        )

        try:
            await app.connect()
            yield app
        finally:
            await app.disconnect()
            await asyncio.sleep(CONNECT_DELAY_S)

    async def restore_backup(
        self, backup: zigpy.backups.NetworkBackup, **kwargs: Any
    ) -> None:
        """Restore the provided network backup, passing through kwargs."""
        if self.current_settings is not None and self.current_settings.supersedes(
            self.chosen_backup
        ):
            return

        async with self._connect_zigpy_app() as app:
            await app.backups.restore_backup(backup, **kwargs)

    def parse_radio_type(self, radio_type: str) -> RadioType:
        """Parse a radio type name, accounting for past aliases."""
        if radio_type == "efr32":
            return RadioType.ezsp

        return RadioType[radio_type]

    async def detect_radio_type(self) -> bool:
        """Probe all radio types on the current port."""
        for radio in AUTOPROBE_RADIOS:
            _LOGGER.debug("Attempting to probe radio type %s", radio)

            dev_config = radio.controller.SCHEMA_DEVICE(
                {CONF_DEVICE_PATH: self.device_path}
            )
            probe_result = await radio.controller.probe(dev_config)

            if not probe_result:
                continue

            # Radio library probing can succeed and return new device settings
            if isinstance(probe_result, dict):
                dev_config = probe_result

            self.radio_type = radio
            self.device_settings = dev_config

            return True

        return False

    async def async_load_network_settings(self, create_backup: bool = False) -> None:
        """Connect to the radio and load its current network settings."""
        async with self._connect_zigpy_app() as app:
            # Check if the stick has any settings and load them
            try:
                await app.load_network_info()
            except NetworkNotFormed:
                pass
            else:
                self.current_settings = zigpy.backups.NetworkBackup(
                    network_info=app.state.network_info,
                    node_info=app.state.node_info,
                )

                if create_backup:
                    await app.backups.create_backup()

            # The list of backups will always exist
            self.backups = app.backups.backups.copy()

    async def async_form_network(self) -> None:
        """Form a brand new network."""
        async with self._connect_zigpy_app() as app:
            await app.form_network()

    async def async_reset_adapter(self) -> None:
        """Reset the current adapter."""
        async with self._connect_zigpy_app() as app:
            await app.reset_network_info()

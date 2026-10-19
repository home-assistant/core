"""Coordinators for the Airobot integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusUnit
from pyairobotmodbus import AirobotModbusClient
from pyairobotmodbus.exceptions import AirobotError as VUError, AirobotReadError
from pyairobotmodbus.models import AirobotData as AirobotVUData, AirobotIdentity
from pyairobotrest import AirobotClient
from pyairobotrest.exceptions import AirobotAuthError, AirobotConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import AirobotData

_LOGGER = logging.getLogger(__name__)

# Update interval - the devices measure air every 30 seconds
UPDATE_INTERVAL = timedelta(seconds=30)

type AirobotConfigEntry = ConfigEntry[
    AirobotDataUpdateCoordinator | AirobotVUCoordinator
]


class AirobotDataUpdateCoordinator(DataUpdateCoordinator[AirobotData]):
    """Class to manage fetching Airobot data."""

    config_entry: AirobotConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AirobotConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        session = async_get_clientsession(hass)

        self.client = AirobotClient(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )

    @override
    async def _async_update_data(self) -> AirobotData:
        """Fetch data from API endpoint."""
        try:
            status, settings = await asyncio.gather(
                self.client.get_statuses(),
                self.client.get_settings(),
            )
        except AirobotAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except AirobotConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err

        return AirobotData(status=status, settings=settings)


class AirobotVUCoordinator(DataUpdateCoordinator[AirobotVUData]):
    """Class to manage fetching Airobot VU data via Modbus."""

    config_entry: AirobotConfigEntry
    identity: AirobotIdentity | None = None

    def __init__(
        self, hass: HomeAssistant, entry: AirobotConfigEntry, unit: ModbusUnit
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = AirobotModbusClient(unit)
        self._verify_identity = True
        entry.async_on_unload(unit.on_connection_lost(self._async_link_lost))

    @callback
    def _async_link_lost(self) -> None:
        """Check the unit's identity again once the link reconnects."""
        self._verify_identity = True

    async def _async_verify_identity(self) -> None:
        """Make sure the configured unit is the one answering at the host."""
        try:
            identity = await self.client.async_get_identity()
        except AirobotReadError:
            # Firmware without the undocumented identity registers
            identity = None
        mac = self.config_entry.unique_id
        if (
            identity is not None
            and mac is not None
            and format_mac(identity.mac_address) != mac
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_ventilation_unit",
                translation_placeholders={"host": self.config_entry.data[CONF_HOST]},
            )
        self.identity = identity
        self._verify_identity = False

    @override
    async def _async_update_data(self) -> AirobotVUData:
        """Fetch data from the Modbus device."""
        try:
            if self._verify_identity:
                await self._async_verify_identity()
            return await self.client.async_get_data()
        except VUError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err

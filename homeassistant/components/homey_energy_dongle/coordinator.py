"""WebSocket telegram coordinator for the Homey Energy Dongle."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

from dsmr_parser.objects import MbusDevice, Telegram
from homey_energy_dongle_ws import (
    ConnectionLimitError,
    EnergyDongleClient,
    HomeyWebSocketError,
    LocalApiDisabledError,
)
from homey_energy_dongle_ws.parser import TELEGRAM_SPECIFICATIONS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DSMR_VERSION, CONF_WS_PATH, DOMAIN, IDENTIFIER_FIELDS

_LOGGER = logging.getLogger(__name__)

# DSMR 4 meters send a telegram every 10 seconds, DSMR 5 meters every second.
TELEGRAM_TIMEOUT = 60
RECONNECT_INTERVAL = 30

type HomeyEnergyDongleConfigEntry = ConfigEntry[HomeyEnergyDongleCoordinator]


def create_client(data: Mapping[str, Any]) -> EnergyDongleClient:
    """Create a client that raises on disconnect, so the caller owns retrying."""
    return EnergyDongleClient(
        data[CONF_HOST],
        port=data[CONF_PORT],
        path=data[CONF_WS_PATH],
        reconnect=False,
        dsmr_version=data.get(CONF_DSMR_VERSION),
    )


def meter_identifier(telegram: Telegram) -> str | None:
    """Return the electricity meter's identifier, if its profile reports one."""
    return next(
        (
            str(obj.value)
            for field in IDENTIFIER_FIELDS
            if (obj := getattr(telegram, field, None)) is not None
        ),
        None,
    )


def mbus_equipment_identifier(device: MbusDevice) -> str | None:
    """Return the identifier the meter reports."""
    if identifier := getattr(device, "MBUS_EQUIPMENT_IDENTIFIER", None):
        return str(identifier.value)
    return None


def meters(
    telegram: Telegram, entry: HomeyEnergyDongleConfigEntry
) -> dict[str, Telegram | MbusDevice]:
    """Map the serial of each meter in the telegram to its readings.

    A meter is its own identity, so a replaced meter or another dongle on the
    same address shows up as another meter. Only telegrams with a checksum
    are trusted for that, as a corrupted identifier would look like another
    meter. Otherwise meters fall back to the entry and their M-Bus channel.
    """
    version = entry.data[CONF_DSMR_VERSION]
    checked = TELEGRAM_SPECIFICATIONS[version]["checksum_support"]
    electricity = (checked and meter_identifier(telegram)) or (
        f"{entry.entry_id}_electricity"
    )
    readings: dict[str, Telegram | MbusDevice] = {electricity: telegram}
    for device in getattr(telegram, "MBUS_DEVICES", []):
        serial = (checked and mbus_equipment_identifier(device)) or (
            f"{electricity}_mbus{device.channel_id}"
        )
        readings[serial] = device
    return readings


class HomeyEnergyDongleCoordinator(DataUpdateCoordinator[Telegram]):
    """Keep the latest telegram pushed over the dongle's WebSocket."""

    config_entry: HomeyEnergyDongleConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HomeyEnergyDongleConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=entry.title)
        self._client = create_client(entry.data)
        self._telegrams = self._client.stream_parsed(skip_parse_errors=True)

    def _create_issue(self, key: str) -> None:
        """Record a repair for a dongle rejection the user can fix."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{key}_{self.config_entry.entry_id}",
            config_entry_id=self.config_entry.entry_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=key,
            translation_placeholders={"name": self.config_entry.title},
        )

    async def _async_next_telegram(self) -> Telegram:
        """Wait for the next telegram on the open stream."""
        try:
            async with asyncio.timeout(TELEGRAM_TIMEOUT):
                telegram = await anext(self._telegrams)
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="telegram_timeout",
                translation_placeholders={"timeout": str(TELEGRAM_TIMEOUT)},
            ) from err
        except LocalApiDisabledError as err:
            self._create_issue("local_api_disabled")
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="local_api_disabled"
            ) from err
        except ConnectionLimitError as err:
            self._create_issue("connection_limit")
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_limit"
            ) from err
        except HomeyWebSocketError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"error": str(err)},
            ) from err
        if self.data is None or not self.last_update_success:
            for key in ("local_api_disabled", "connection_limit"):
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"{key}_{self.config_entry.entry_id}"
                )
        return telegram

    async def async_listen(self) -> None:
        """Push telegrams to the entities and reconnect after failures."""
        while True:
            try:
                telegram = await self._async_next_telegram()
            except UpdateFailed as err:
                # A failed stream is finished, so the next read opens a new connection.
                self._telegrams = self._client.stream_parsed(skip_parse_errors=True)
                self.async_set_update_error(err)
                await asyncio.sleep(RECONNECT_INTERVAL)
                continue
            if not self.last_update_success:
                self.logger.info("Receiving telegrams from %s again", self.name)
            self.async_set_updated_data(telegram)

    @override
    async def async_shutdown(self) -> None:
        """Close the WebSocket, as the dongle only allows two connections."""
        await super().async_shutdown()
        await self._client.aclose()

    @override
    async def _async_update_data(self) -> Telegram:
        """Wait for the first telegram, then keep the pushed one on requests."""
        if self.data is None:
            return await self._async_next_telegram()
        if not self.last_update_success:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="not_connected"
            )
        return self.data

"""Data update coordinator for Zeversolar."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TypedDict

import aiohttp
import zeversolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, HTTP_TIMEOUT

_LOGGER = logging.getLogger(__name__)

type ZeversolarConfigEntry = ConfigEntry[ZeversolarCoordinator]


class ZeversolarCoordinatorData(TypedDict):
    """Typed structure for coordinator data."""

    inverter_data: zeversolar.ZeverSolarData
    power_limit: int


class ZeversolarCoordinator(DataUpdateCoordinator[ZeversolarCoordinatorData]):
    """Coordinator that fetches both production data and power limit state."""

    config_entry: ZeversolarConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ZeversolarConfigEntry) -> None:
        """Initialize the coordinator."""
        self.host: str = entry.data[CONF_HOST]
        self._client: zeversolar.ZeverSolarClient = zeversolar.ZeverSolarClient(
            host=self.host
        )
        self.ramp_lock = asyncio.Lock()
        self.power_limit_supported = False  # set True after successful probe
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def async_probe_power_limit_api(self) -> bool:
        """Validate that adv.cgi returns a response we can safely parse.

        Checks:
        - At least 15 lines in the response
        - Field 8  (enlim)     is a positive integer (>0 means enabled)
        - Field 11 (ac_value1) is an integer in the range 5–100
        - Field 14 (ac_mode)   is 0 or 1
        """
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"http://{self.host}/adv.cgi",
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
            ) as resp:
                text = await resp.text()
                lines = text.splitlines()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Power limit API probe failed — cannot reach adv.cgi: %s", err
            )
            return False

        if len(lines) < 15:
            _LOGGER.warning(
                "Power limit API probe failed — adv.cgi returned %d lines, expected ≥15",
                len(lines),
            )
            return False

        try:
            enlim = int(lines[8].strip())
            ac_value1 = int(float(lines[11].strip()))
            ac_mode = int(lines[14].strip())
        except (ValueError, IndexError) as err:
            _LOGGER.warning(
                "Power limit API probe failed — cannot parse adv.cgi fields: %s", err
            )
            return False

        if enlim == 0:
            # enlim=0 means power limiting is disabled in the inverter's own settings.
            # Enable it via the inverter web interface before using output controls.
            _LOGGER.warning(
                "Power limit API probe failed — field 8 (enlim) is 0, "
                "power limiting is disabled on the inverter "
                "(enable it in the inverter web interface, then reload the integration)"
            )
            return False

        if enlim < 0:
            _LOGGER.warning(
                "Power limit API probe failed — field 8 (enlim) is %r, expected a positive integer",
                enlim,
            )
            return False

        if ac_mode not in (0, 1):
            _LOGGER.warning(
                "Power limit API probe failed — field 14 (ac_mode) is %r, expected 0 or 1",
                ac_mode,
            )
            return False

        if not (5 <= ac_value1 <= 100):
            _LOGGER.warning(
                "Power limit API probe failed — field 11 (ac_value1) is %r, expected 5–100",
                ac_value1,
            )
            return False

        _LOGGER.debug(
            "Power limit API probe passed (enlim=%d, ac_value1=%d, ac_mode=%d)",
            enlim,
            ac_value1,
            ac_mode,
        )
        return True

    async def _async_update_data(self) -> ZeversolarCoordinatorData:
        """Fetch production data and current power limit from the inverter."""
        try:
            inverter_data = await self.hass.async_add_executor_job(
                self._client.get_data
            )
        except Exception as err:
            raise UpdateFailed(f"Cannot reach inverter at {self.host}: {err}") from err

        power_limit = (self.data or {}).get("power_limit", 100)
        if self.power_limit_supported:
            try:
                power_limit = await self._fetch_power_limit()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not fetch power limit from adv.cgi: %s", err)

        return ZeversolarCoordinatorData(
            inverter_data=inverter_data,
            power_limit=power_limit,
        )

    async def _fetch_power_limit(self) -> int:
        """Read current power limit % from adv.cgi (field index 11)."""
        session = async_get_clientsession(self.hass)
        async with session.get(
            f"http://{self.host}/adv.cgi",
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            text = await resp.text()
            lines = text.splitlines()
            if len(lines) < 12:
                raise ValueError(f"adv.cgi returned {len(lines)} lines, expected ≥12")
            return int(float(lines[11].strip()))

"""The OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from collections.abc import Callable
import datetime as dt
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import CET
from .coordinator import OMIEDailyCoordinator, spot_price
from .model import OMIESources

_LOGGER = logging.getLogger(__name__)


def _cet_date(plus: dt.timedelta = dt.timedelta()) -> Callable[[], dt.date]:
    return lambda: utcnow().astimezone(CET).date() + plus


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # OMIE data is in the CET timezone so today's date locally may be tomorrow
    # or yesterday in that timezone. we fetch (today-1,today,today+1) as that is
    # needed to correctly handle the hours when PT and ES are on different dates.

    entry.runtime_data = OMIESources(
        today=OMIEDailyCoordinator(
            hass,
            "spot_today",
            market_updater=spot_price,
            market_date=_cet_date(),
        ),
        tomorrow=OMIEDailyCoordinator(
            hass,
            "spot_tomorrow",
            market_updater=spot_price,
            market_date=_cet_date(plus=dt.timedelta(days=1)),
            none_before="13:30",
        ),
        yesterday=OMIEDailyCoordinator(
            hass,
            "spot_yesterday",
            market_updater=spot_price,
            market_date=_cet_date(plus=dt.timedelta(days=-1)),
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, Platform.SENSOR)

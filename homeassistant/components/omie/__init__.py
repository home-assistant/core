"""The OMIE - Spain and Portugal electricity prices integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import CET, DOMAIN
from .coordinator import OMIEDailyCoordinator, spot_price
from .model import OMIESources

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    # OMIE data is in the CET timezone so today's date locally may be tomorrow
    # or yesterday in that timezone. we fetch (today-1,today,today+1) as that is
    # needed to correctly handle the hours when PT and ES are on different dates.
    cet_today = lambda: utcnow().astimezone(CET).date()
    cet_tomorrow = lambda: cet_today() + timedelta(days=1)
    cet_yesterday = lambda: cet_today() - timedelta(days=1)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = OMIESources(
        today=OMIEDailyCoordinator(
            hass,
            "omie_spot_today",
            market_updater=spot_price,
            market_date=cet_today,
        ),
        tomorrow=OMIEDailyCoordinator(
            hass,
            "omie_spot_tomorrow",
            market_updater=spot_price,
            market_date=cet_tomorrow,
            none_before="13:30",
        ),
        yesterday=OMIEDailyCoordinator(
            hass,
            "omie_spot_yesterday",
            market_updater=spot_price,
            market_date=cet_yesterday,
        ),
    )

    return await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

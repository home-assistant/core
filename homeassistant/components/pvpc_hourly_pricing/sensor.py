"""
Sensor to collect the reference daily prices of electricity ('PVPC') in Spain.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
from datetime import date, datetime, timedelta
import logging
from random import randint
from typing import Dict, List, Optional

import aiohttp
import async_timeout
from pytz import UTC, timezone

from homeassistant import config_entries
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from . import SENSOR_SCHEMA
from .const import ATTR_TARIFF, DEFAULT_TIMEOUT, DOMAIN, TARIFFS

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SENSOR_SCHEMA.schema)

_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"
_PRECISION = 5
_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)
_TARIFF_KEYS = dict(zip(TARIFFS, ["GEN", "NOC", "VHC"]))

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
_REFERENCE_TZ = timezone("Europe/Madrid")

ATTR_PRICE = "price"
ICON = "mdi:currency-eur"
UNIT = "€/kWh"


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_devices, discovery_info=None
):
    """
    Set up the electricity price sensor as a sensor platform.

    ```yaml
    sensor:
      - platform: pvpc_hourly_pricing
        name: pvpc_manual_sensor
        tariff: normal

      - platform: pvpc_hourly_pricing
        name: pvpc_manual_sensor_2
        tariff: discrimination
        timeout: 8
    ```
    """
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, data=config, context={"source": config_entries.SOURCE_IMPORT}
        )
    )
    return True


async def update_listener(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Update selected tariff for sensor."""
    if entry.options[ATTR_TARIFF] != entry.data[ATTR_TARIFF]:
        entry.data[ATTR_TARIFF] = entry.options[ATTR_TARIFF]
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry, async_add_entities
):
    """Set up the electricity price sensor from config_entry."""
    if not config_entry.update_listeners:
        config_entry.add_update_listener(update_listener)

    name = config_entry.data[CONF_NAME]
    entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)
    async_add_entities(
        [
            ElecPriceSensor(
                websession=async_get_clientsession(hass),
                name=name,
                entity_id=entity_id,
                tariff=config_entry.data[ATTR_TARIFF],
                timeout=config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )
        ],
        True,
    )


def extract_prices_for_tariff(data: List[dict], tariff: str) -> Dict[datetime, float]:
    """
    PVPC data extractor.

    Extract hourly prices for the selected tariff from the JSON daily file download
    of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
    for the _Voluntary Price for Small Consumers_
    (Precio Voluntario para el Pequeño Consumidor, PVPC).

    Prices are referenced with datetimes in UTC.
    """
    key = _TARIFF_KEYS[tariff]
    ts_init = (
        datetime.strptime(data[0]["Dia"], "%d/%m/%Y")
        .astimezone(_REFERENCE_TZ)
        .astimezone(UTC)
    )
    return {
        ts_init
        + timedelta(hours=i): round(
            float(values_hour[key].replace(",", ".")) / 1000.0, _PRECISION
        )
        for i, values_hour in enumerate(data)
    }


class ElecPriceSensor(RestoreEntity):
    """Class to hold the prices of electricity as a sensor."""

    def __init__(self, websession, name, entity_id, tariff, timeout):
        """Initialize the sensor object."""
        self._websession = websession
        self._name = name
        self.entity_id = entity_id
        self._tariff = tariff
        self._timeout = timeout
        self._num_retries = 0
        self._state = None
        self._state_available = False
        self._data_source_available = True
        self._attributes = None
        self._current_prices: Dict[datetime, float] = {}

        self._init_done = False
        self._hourly_tracker = None
        self._price_tracker = None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel listeners for sensor updates."""
        self._hourly_tracker()
        self._price_tracker()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._state = state.state

        # Update 'state' value in hour changes
        self._hourly_tracker = async_track_time_change(
            self.hass, self.async_update, second=[0], minute=[0]
        )
        # Update prices at random time, 2 times/hour (don't want to upset API)
        random_minute = randint(1, 29)
        mins_update = [random_minute, random_minute + 30]
        self._price_tracker = async_track_time_change(
            self.hass, self.async_update_prices, second=[0], minute=mins_update
        )
        _LOGGER.debug(
            "Setup of price sensor %s (%s) with tariff '%s', "
            "updating prices each hour at %s min",
            self.name,
            self.entity_id,
            self._tariff,
            mins_update,
        )
        await self.async_update_prices()
        self._init_done = True
        await self.async_update_ha_state(True)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return "_".join([DOMAIN, "sensor", self.entity_id])

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the price of electricity."""
        return UNIT

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._state_available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _process_state_and_attributes(self) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets, with correspondence
        with the main timezone in Spain, but they are stored with UTC datetimes.
        """

        def _local(dt_utc: datetime) -> datetime:
            return dt_utc.astimezone(self.hass.config.time_zone)

        attributes = {ATTR_ATTRIBUTION: _ATTRIBUTION, ATTR_TARIFF: self._tariff}
        utc_time = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        actual_time = _local(utc_time)
        if len(self._current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(_REFERENCE_TZ)
                .replace(hour=0)
                .astimezone(dt_util.UTC)
            )
            self._current_prices = {
                key_ts: price
                for key_ts, price in self._current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self._state = self._current_prices[utc_time]
            self._state_available = True
        except KeyError:
            self._state_available = False
            self._attributes = attributes
            return False

        # generate sensor attributes
        prices_sorted = dict(sorted(self._current_prices.items(), key=lambda x: x[1]))
        attributes["min_price"] = min(self._current_prices.values())
        attributes["min_price_at"] = _local(next(iter(prices_sorted))).hour
        attributes["next_best_at"] = list(
            map(
                lambda x: _local(x).hour,
                filter(lambda x: x >= utc_time, prices_sorted.keys()),
            )
        )
        for ts_utc, price_h in self._current_prices.items():
            ts_local = _local(ts_utc)
            if ts_local.day > actual_time.day:
                attr_key = f"price_next_day_{ts_local.hour:02d}h"
            else:
                attr_key = f"price_{ts_local.hour:02d}h"
            if attr_key in attributes:  # DST change with duplicated hour :)
                attr_key += "_d"
            attributes[attr_key] = price_h

        self._attributes = attributes
        return True

    async def async_update(self, *_args):
        """Update the sensor state."""
        if not self._init_done:
            # abort until added_to_hass is finished
            return

        if self._process_state_and_attributes():
            await self.async_update_ha_state()
        else:
            # If no prices present, download and schedule a future state update
            self._state_available = False
            self.async_schedule_update_ha_state()

            if self._data_source_available:
                _LOGGER.debug(
                    "[%s]: Downloading prices as there are no valid ones",
                    self.entity_id,
                )
                async_track_point_in_time(
                    self.hass,
                    self.async_update,
                    dt_util.now() + timedelta(seconds=self._timeout),
                )
            await self.async_update_prices()

    async def _download_official_data(self, day: date) -> List[dict]:
        """Make GET request to 'api.esios.ree.es' to retrieve hourly prices."""
        url = _RESOURCE.format(day=day)
        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                resp = await self._websession.get(url)
                if resp.status < 400:
                    data = await resp.json()
                    return data["PVPC"]
        except KeyError:
            _LOGGER.debug("Bad try on getting prices for %s", day)
        except asyncio.TimeoutError:  # pragma: no cover
            if self._data_source_available:
                _LOGGER.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError:  # pragma: no cover
            if self._data_source_available:
                _LOGGER.warning("Client error in '%s'", url)
        return {}

    async def async_update_prices(self, *_args):
        """Update electricity prices from the ESIOS API."""
        localized_now = dt_util.utcnow().astimezone(_REFERENCE_TZ)
        data = await self._download_official_data(localized_now.date())
        if not data and self._data_source_available:
            self._num_retries += 1
            if self._num_retries > 2:
                _LOGGER.warning(
                    "Repeated bad data update, mark component as unavailable source"
                )
                self._data_source_available = False
                return

            _LOGGER.debug(
                "Bad update[retry:%d], will try again in %d s",
                self._num_retries,
                3 * self._timeout,
            )
            async_track_point_in_time(
                self.hass,
                self.async_update_prices,
                dt_util.now() + timedelta(seconds=3 * self._timeout),
            )
            return

        if not data:
            _LOGGER.debug(
                "Data source unavailable since %s",
                self.hass.states.get(self.entity_id).last_changed,
            )
            return

        prices = extract_prices_for_tariff(data, self._tariff)
        self._num_retries = 0
        self._current_prices.update(prices)
        if not self._data_source_available:
            self._data_source_available = True
            _LOGGER.warning(
                "Component has recovered data access. Was unavailable since %s",
                self.hass.states.get(self.entity_id).last_changed,
            )
            self.async_schedule_update_ha_state(True)

        # At evening, it is possible to retrieve next day prices
        if localized_now.hour >= 20:
            next_day = (localized_now + timedelta(days=1)).date()
            data_next_day = await self._download_official_data(next_day)
            if data_next_day:
                prices_fut = extract_prices_for_tariff(data_next_day, self._tariff)
                self._current_prices.update(prices_fut)

        _LOGGER.debug(
            "Download done for %s, now with %d prices from %s UTC",
            self.entity_id,
            len(self._current_prices),
            list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

"""
Sensor to collect the reference daily prices of electricity ('PVPC') in Spain.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
from datetime import date, datetime, timedelta
import logging
from random import randint
from typing import Dict, Optional

import aiohttp
import async_timeout
from dateutil.parser import parse
from pytz import timezone
import xmltodict

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
from .const import ATTR_TARIFF, DOMAIN, TARIFFS

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SENSOR_SCHEMA.schema)

_RESOURCE = "https://api.esios.ree.es/archives/80/download?date={day:%Y-%m-%d}"
_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"

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
        tariff: discriminacion
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
                timeout=config_entry.data.get(CONF_TIMEOUT, 5),
            )
        ],
        True,
    )


def extract_prices_for_tariff(xml_data: str, tariff: int = 2) -> Dict[datetime, float]:
    """
    PVPC xml data extractor.

    Extract hourly prices for the selected tariff from the xml daily file download
    of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
    for the _Voluntary Price for Small Consumers_
    (Precio Voluntario para el Pequeño Consumidor, PVPC).

    Prices are referenced with datetimes in UTC.
    """
    data = xmltodict.parse(xml_data)["PVPCDesgloseHorario"]

    str_horiz = data["Horizonte"]["@v"]
    ts_init: datetime = next(map(parse, str_horiz.split("/")))

    tariff_id = f"Z0{tariff}"
    prices = next(
        filter(
            lambda x: (
                x["TerminoCosteHorario"]["@v"] == "FEU"
                and x["TipoPrecio"]["@v"] == tariff_id
            ),
            data["SeriesTemporales"],
        )
    )

    price_values = {
        ts_init + timedelta(hours=i): round(float(pair["Ctd"]["@v"]), 5)
        for i, pair in enumerate(prices["Periodo"]["Intervalo"])
    }
    return price_values


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
        # Update prices at random time, 3 times/hour (don't want to upset API)
        random_minute = randint(1, 19)
        mins_update = [random_minute + 20 * i for i in range(3)]
        self._price_tracker = async_track_time_change(
            self.hass, self.async_update_prices, second=[0], minute=mins_update
        )
        _LOGGER.info(
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

        def _local(ts: datetime) -> datetime:
            return ts.astimezone(self.hass.config.time_zone)

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
        except KeyError:  # pragma: no cover
            self._state_available = False
            return False

        # generate sensor attributes
        prices_sorted = dict(sorted(self._current_prices.items(), key=lambda x: x[1]))
        attributes = {ATTR_ATTRIBUTION: _ATTRIBUTION, ATTR_TARIFF: self._tariff}
        attributes["min price"] = min(self._current_prices.values())
        attributes["min price at"] = _local(next(iter(prices_sorted))).hour
        attributes["next best at"] = list(
            map(
                lambda x: _local(x).hour,
                filter(lambda x: x >= utc_time, prices_sorted.keys()),
            )
        )
        for ts_utc, price_h in self._current_prices.items():
            ts_local = _local(ts_utc)
            if ts_local.day > actual_time.day:
                attr_key = f"price next day {ts_local.hour:02d}h"
            else:
                attr_key = f"price {ts_local.hour:02d}h"
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
        else:  # pragma: no cover
            # If no prices present, download and schedule a future state update
            self._state = None
            if self._data_source_available:
                _LOGGER.warning(
                    "[%s]: Downloading prices as there are no valid ones",
                    self.entity_id,
                )
                async_track_point_in_time(
                    self.hass,
                    self.async_update,
                    dt_util.now() + timedelta(seconds=self._timeout),
                )
            await self.async_update_prices()

    async def _download_official_data(self, day: date) -> Optional[str]:
        """Make GET request to 'api.esios.ree.es' to retrieve hourly prices."""
        url = _RESOURCE.format(day=day)
        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                resp = await self._websession.get(url)
                if resp.status < 400:
                    text = await resp.text()
                    return text
        except asyncio.TimeoutError:  # pragma: no cover
            _LOGGER.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError:  # pragma: no cover
            _LOGGER.error("Client error in '%s'", url)
        return None  # pragma: no cover

    async def async_update_prices(self, *args):
        """Update electricity prices from the ESIOS API."""
        localized_now = dt_util.utcnow().astimezone(_REFERENCE_TZ)
        text = await self._download_official_data(localized_now.date())
        if text is None and self._data_source_available:  # pragma: no cover
            self._num_retries += 1
            if self._num_retries > 2:
                _LOGGER.error("Bad data update")
                self._data_source_available = False
                return

            _LOGGER.warning(
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

        tariff_number = TARIFFS.index(self._tariff) + 1
        prices = extract_prices_for_tariff(text, tariff_number)
        self._num_retries = 0
        self._current_prices.update(prices)
        self._data_source_available = True

        # At evening, it is possible to retrieve next day prices
        if localized_now.hour >= 20:
            try:
                next_day = (localized_now + timedelta(days=1)).date()
                text_next_day = await self._download_official_data(next_day)
                prices_fut = extract_prices_for_tariff(text_next_day, tariff_number)
                self._current_prices.update(prices_fut)
            except xmltodict.expat.ExpatError:  # pragma: no cover
                _LOGGER.debug("Bad try on getting future prices")

        _LOGGER.debug(
            "Download done for %s, now with %d prices from %s UTC",
            self.entity_id,
            len(self._current_prices),
            list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

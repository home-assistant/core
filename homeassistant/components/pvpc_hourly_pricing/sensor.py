"""
Sensor to collect the reference daily prices of electricity ('PVPC') in Spain.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
from datetime import date, timedelta
import logging
from random import randint
from typing import List, Optional, Tuple

import aiohttp
import async_timeout
from dateutil.parser import parse
from pytz import timezone
import xmltodict

from homeassistant import config_entries
from homeassistant.components.sensor import ENTITY_ID_FORMAT
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

from .const import ATTR_TARIFF, DOMAIN, TARIFFS

_LOGGER = logging.getLogger(__name__)

_RESOURCE = "https://api.esios.ree.es/archives/80/download?date={day:%Y-%m-%d}"
_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"

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

    async_add_entities(
        [
            ElecPriceSensor(
                hass,
                websession=async_get_clientsession(hass),
                name=config_entry.data[CONF_NAME],
                tariff=config_entry.data[ATTR_TARIFF],
                timeout=config_entry.data.get(CONF_TIMEOUT, 5),
            )
        ],
        True,
    )


def extract_prices_for_tariff(
    xml_data: str, tz: timezone, tariff: int = 2
) -> Tuple[date, List[float]]:
    """
    PVPC xml data extractor.

    Extract hourly prices for the selected tariff from the xml daily file download
    of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
    for the _Voluntary Price for Small Consumers_
    (Precio Voluntario para el Pequeño Consumidor, PVPC).
    """
    data = xmltodict.parse(xml_data)["PVPCDesgloseHorario"]

    str_horiz = data["Horizonte"]["@v"]
    day: date = parse(str_horiz.split("/")[0]).astimezone(tz).date()

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

    price_values = [
        round(float(pair["Ctd"]["@v"]), 5) for pair in prices["Periodo"]["Intervalo"]
    ]
    return day, price_values


class ElecPriceSensor(RestoreEntity):
    """Class to hold the prices of electricity as a sensor."""

    def __init__(self, hass, websession, name, tariff, timeout):
        """Initialize the sensor object."""
        self.hass = hass
        self._websession = websession
        self._name = name
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._name, hass=self.hass
        )
        self._tariff = tariff
        self._timeout = timeout
        self._num_retries = 0
        self._state = None
        self._attributes = None
        self._today_prices = None
        self._tomorrow_prices = None
        self._init_done = False

        # Update 'state' value 2 times/hour
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
            f"Setup of price sensor {self.name} ({self.entity_id}) "
            f"for tariff '{self._tariff}', "
            f"updating data at {mins_update} min, each hour"
        )

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
            self._today_prices = [
                state.attributes[k] for k in state.attributes if k.startswith("price")
            ]
            _LOGGER.debug(
                f"RestoreState[{self.entity_id}]: "
                f"Loaded {len(self._today_prices)} prices"
            )

        self._init_done = True
        await self.async_update_prices()
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
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _get_current_value(self, current_hour):
        """
        Extract current price from today prices array.

        In DST days, this array will have 23 or 25 values, instead of the expected 24.
        """
        if len(self._today_prices) == 23 and current_hour > 2:
            return self._today_prices[current_hour - 1]
        elif len(self._today_prices) == 25 and current_hour > 2:
            return self._today_prices[current_hour + 1]
        return self._today_prices[current_hour]

    def _process_state_and_attributes(self):
        """Generate the current state and sensor attributes."""
        actual_hour = dt_util.now(self.hass.config.time_zone).hour
        if self._tomorrow_prices is not None and actual_hour < 3:
            # remove 'tomorrow prices' as now they refer to 'today'
            self._tomorrow_prices = None

        if self._today_prices is None:
            _LOGGER.info(f"Abort process, no values!!")
            _LOGGER.critical(f"Abort process, no values!!")
            return

        # set current price
        self._state = self._get_current_value(actual_hour)

        prices = self._today_prices.copy()
        if self._tomorrow_prices is not None:
            prices += self._tomorrow_prices

        # generate sensor attributes
        prices_sorted = dict(
            sorted({i: p for i, p in enumerate(prices)}.items(), key=lambda x: x[1],)
        )
        attributes = {ATTR_ATTRIBUTION: _ATTRIBUTION, ATTR_TARIFF: self._tariff}
        attributes["min price"] = min(prices)
        attributes["min price at"] = next(iter(prices_sorted))
        attributes["next best at"] = list(
            filter(lambda x: x >= actual_hour, prices_sorted.keys())
        )

        for i, p in enumerate(self._today_prices):
            attributes[f"price {i:02d}h"] = p
        if self._tomorrow_prices is not None:
            for i, p in enumerate(self._tomorrow_prices):
                attributes[f"price next day {i:02d}h"] = p

        self._attributes = attributes

    async def async_update(self, *_args):
        """Update the sensor state."""
        if not self._init_done:
            # abort until added_to_hass is finished
            return

        if self._today_prices:
            self._process_state_and_attributes()
            await self.async_update_ha_state()
        else:
            # If no prices present, download and schedule a future state update
            self._state = None
            _LOGGER.debug(
                "[%s]: Downloading prices, updating after %d seconds",
                self.entity_id,
                self._timeout,
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
                else:
                    _LOGGER.warning(
                        "Request error in '%s' [status: %d]", url, resp.status
                    )
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError:
            _LOGGER.error("Client error in '%s'", url)
        return None

    async def async_update_prices(self, *args):
        """Update electricity prices from the ESIOS API."""
        tz = self.hass.config.time_zone
        now = args[0].astimezone(tz) if args else dt_util.now(tz)
        text = await self._download_official_data(now.date())
        if text is None:
            self._num_retries += 1
            if self._num_retries > 3:
                _LOGGER.error("Bad data update")
                return

            f_log = _LOGGER.warning if self._num_retries > 1 else _LOGGER.info
            f_log("Bad update, will try again in %d s", 3 * self._timeout)
            async_track_point_in_time(
                self.hass,
                self.async_update_prices,
                dt_util.now() + timedelta(seconds=3 * self._timeout),
            )
            return

        tariff_number = TARIFFS.index(self._tariff) + 1
        day, prices = extract_prices_for_tariff(text, tz, tariff_number)
        self._num_retries = 0
        self._today_prices = prices

        # At evening, it is possible to retrieve 'tomorrow' prices
        if now.hour >= 20:
            try:
                text_tomorrow = await self._download_official_data(
                    (now + timedelta(days=1)).date()
                )
                day_fut, prices_fut = extract_prices_for_tariff(
                    text_tomorrow, tz, tariff_number
                )
                _LOGGER.debug(
                    "Setting tomorrow (%s) prices: %s",
                    day_fut.strftime("%Y-%m-%d"),
                    str(prices),
                )
                self._tomorrow_prices = prices_fut
                return
            except xmltodict.expat.ExpatError:
                _LOGGER.debug("Bad try on getting future prices")

        self._tomorrow_prices = None
        _LOGGER.debug(f"Download done for {self.entity_id}")

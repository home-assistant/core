"""The Solcast Solar integration."""
from __future__ import annotations

import base64
import datetime
import json
import logging
import traceback
from datetime import date, timedelta, timezone
from operator import itemgetter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                        UpdateFailed)
from isodate import parse_datetime, parse_duration
from pysolcast.exceptions import RateLimitExceeded, SiteError, ValidationError
from pysolcast.rooftop import RooftopSite
from requests import get

from .const import CONF_APIKEY, CONF_POLL_INTERVAL, CONF_ROOFTOP, DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    unloaded = await async_unload_entry(hass, entry)
    if unloaded:
        await async_setup_entry(hass, entry)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solcast Solar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SolcastDataCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    async_track_utc_time_change(hass, coordinator.update_hass, minute=0,second=0, local=True)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def options_updated_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.data[DOMAIN].async_request_refresh()

class SolcastDataCoordinator(DataUpdateCoordinator):
    """Solcast Data Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.entry: ConfigEntry = entry
        self.savedata: dict | None = None
        self.wh_days: dict[datetime.datetime, float] | None = None
        self.wh_hours: dict[datetime.datetime, float] | None = None
        self.api_remaining: int | None = entry.data['apiremaining']
        self.last_update: int | None = entry.data['last_update']
        self.poll_interval = entry.options[CONF_POLL_INTERVAL]
        api_key = entry.options.get(CONF_APIKEY)
        rooftop_id = entry.options.get(CONF_ROOFTOP)
        self.client = RooftopSite(api_key, rooftop_id)
        self.logname: str | None = entry.title

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )

    @property
    def energy_production_today(self) -> float:
        """Return estimated energy produced today."""
        return self.day_production(datetime.datetime.now().date())

    @property
    def energy_production_tomorrow(self) -> float:
        """Return estimated energy produced today."""
        return self.day_production(datetime.datetime.now().date() + timedelta(days=1))
    
    def day_production(self, specific_date: date) -> float:
        """Return the day production."""
        for timestamp, production in self.wh_days.items():
            if timestamp.date() == specific_date:
                return production

        return 0

    def sum_energy_production(self, period_hours: int) -> float:
        """Return the sum of the energy production."""
        now = datetime.datetime.now() + timedelta(hours=period_hours)

        total = 0

        for timestamp, wh in self.wh_hours.items():
            if (timestamp.day == now.day) and (timestamp.hour == now.hour):
                total += wh

        return total

    def sum_energy_production_remaining_today(self) -> float:
        """Return the sum of the energy production."""
        now = datetime.datetime.now().astimezone(tz=None)
        nowint = 0
        if now.minute >= 30:
            nowint = int(datetime.datetime.now().strftime("%Y%m%d%H3000"))
        else:
            nowint = int(datetime.datetime.now().strftime("%Y%m%d%H0000"))

        total = 0

        for timestamp, wh in self.wh_hours.items():
            timestamp = timestamp.astimezone(tz=None)
            timestampint = int(timestamp.strftime("%Y%m%d%H%M%S"))
            if (timestamp.day == now.day) and (timestampint > nowint):
                total += wh

        return total
        
    def update_data(self):
        """Get the latest data from Solcast API."""
        _LOGGER.debug("%s - Executing rooftop date update", self.logname)
        
        try:
            forecasts = {}
            time_inbetween = (self.poll_interval * 3600) - 10
            timesince = int(datetime.datetime.now().strftime("%Y%m%d%H%M%S")) - self.last_update

            _doData1 = False
            _doData2 = False
            n = datetime.datetime.now()
            _dontsave = False

            if self.last_update == 19800413000000:
                #never run.. default value
                _LOGGER.debug("%s - First time this integration has been run.. setting up", self.logname)
                _doData1 = True
                _doData2 = True
            elif timesince < time_inbetween:
                _LOGGER.debug("%s - Last update is less than time interval set", self.logname)
                _doData1 = False
            else:
                _LOGGER.debug("%s - Greater then interval hour since last API get", self.logname)
                _doData1 = True
                _doData2 = True

                if n.hour < 5 or n.hour > 19:
                    _LOGGER.debug("%s - Outside of 5am till 7pm polling API time", self.logname)
                    #the API is only polled between 5am and 7pm
                    _doData1 = False

                if n.hour == 10 or n.hour == 12 or n.hour == 14 or n.hour == 16 or n.hour == 19:
                    _LOGGER.debug("%s - API polling for actual forecast data", self.logname)
                    _doData2 = True
                else:
                    _doData2 = False

            try:
                if _doData1 and _doData2:
                    _LOGGER.debug("%s - Polling API for both Forecasts and Actuals data", self.logname)
                    forecasts = self.client.get_forecasts()
                    actuals = self.client.get_estimated_actuals()
                    forecasts = dict({"forecasts": (forecasts.get("forecasts") + actuals.get("estimated_actuals"))})
                elif _doData1:
                    _LOGGER.debug("%s - Only polling API for Forecasts data", self.logname)
                    forecasts = self.client.get_forecasts()
                elif _doData2:
                    _LOGGER.debug("%s - Only polling API for Actuals data", self.logname)
                    forecasts = dict({"forecasts": []})
                    actuals = self.client.get_estimated_actuals()
                    forecasts = dict({"forecasts": (forecasts.get("forecasts") + actuals.get("estimated_actuals"))})
                else:
                    _LOGGER.debug("%s - Not polling API. Loading last saved data", self.logname)
                    _dontsave = True

                if self.api_remaining == 0:
                    self.api_remaining = 50

            except SiteError as err:
                _LOGGER.error("%s - SiteError: %s", self.logname, err)
                _dontsave = True
            except ValidationError as err:
                _LOGGER.error("%s - ValidationError: %s", self.logname, err)
                _dontsave = True
            except RateLimitExceeded as err:
                _LOGGER.error("%s - API rate limit exceeded. Will reset at midnight UTC", self.logname)
                _dontsave = True
                self.api_remaining = 0

            if _dontsave:
                #possible error or just not time to get new data
                try:
                    forecasts = json.loads(base64.urlsafe_b64decode(self.entry.data['data'].encode()).decode())
                    forecasts = dict({"forecasts": forecasts})
                    _LOGGER.debug("%s - Saved data loaded", self.logname)
                except Exception as err:
                    _LOGGER.error(traceback.format_exc())
                
            _lastcheck = datetime.datetime.strptime(str(self.last_update), "%Y%m%d%H%M%S")

            midnightsevenago = datetime.datetime(_lastcheck.year,_lastcheck.month, _lastcheck.day, 0, 0, 0, 0) + timedelta(days=-6)
            midnightsevenago = datetime.datetime.astimezone(midnightsevenago,tz=timezone.utc)

            midnightinsevendays = datetime.datetime(_lastcheck.year, _lastcheck.month, _lastcheck.day, 0, 0, 0, 0) + timedelta(days=6)
            midnightinsevendays = datetime.datetime.astimezone(midnightinsevendays,tz=timezone.utc)

            if self.savedata == None:
                self.savedata = dict({"forecasts": []})

            f = itemgetter('period_end')
            forecastssorted = sorted(forecasts['forecasts'], key=itemgetter('period_end'))

            if len(forecastssorted) > 2:
                pd = parse_datetime(forecastssorted[0]['period_end'])
                if pd.minute == 30:
                    del forecastssorted[0]
                pd = parse_datetime(forecastssorted[-1]['period_end'])
                if pd.minute == 0:
                    del forecastssorted[-1]
            
            forecasts = dict({"forecasts": forecastssorted})

            try:
                wattsbefore = -1
                lastforecast = None
                for forecast in forecasts['forecasts']:
                    # Convert period_end and period. All other fields should already be the correct type
                    forecastdate = parse_datetime(forecast["period_end"]).replace(tzinfo=timezone.utc).astimezone(tz=None)
                    watts = float(forecast["pv_estimate"]) * 1000.0

                    if (forecastdate > midnightsevenago and forecastdate < midnightinsevendays) and not (watts == 0 and wattsbefore == 0):
                        if wattsbefore == 0:
                            #add last forecast
                            lastforecastdate = parse_datetime(lastforecast["period_end"]).replace(tzinfo=timezone.utc).astimezone(tz=None)
                            lastforecast["pv_estimate"] = 0 
                            lastforecast["period_end"] = lastforecastdate
                            lastforecast["period"] = parse_duration(forecast["period"])
                            starttime = lastforecast["period_end"] - lastforecast["period"]
                            lastforecast["period_start"] = starttime
                            found_index = next((index for (index, d) in enumerate(self.savedata.get("forecasts")) if d["period_end"] == lastforecastdate), None)
                            if found_index == None:
                                self.savedata["forecasts"].append(lastforecast)
                            else:
                                self.savedata["forecasts"][found_index] = lastforecast

                        forecast["pv_estimate"] = watts 
                        forecast["period_end"] = forecastdate
                        forecast["period"] = parse_duration(forecast["period"])
                        starttime = forecast["period_end"] - forecast["period"]
                        forecast["period_start"] = starttime
                        found_index = next((index for (index, d) in enumerate(self.savedata.get("forecasts")) if d["period_end"] == forecastdate), None)
                        if found_index == None:
                            self.savedata["forecasts"].append(forecast)
                        else:
                            self.savedata["forecasts"][found_index] = forecast

                    wattsbefore = watts
                    lastforecast = forecast

            except Exception as err:
                _LOGGER.error(traceback.format_exc())
            
            self.wh_days = {}
            self.wh_hours = {}
            try:
                for item in self.savedata["forecasts"]:
                    timestamp = item['period_end']
                    energy = float(item["pv_estimate"]) * 0.5
                    #wh_hours
                    d = datetime.datetime(timestamp.year, timestamp.month, timestamp.day, timestamp.hour , 0, 0)
                    if d in self.wh_hours:
                        self.wh_hours[d] += round(energy, 3)
                    else:
                        self.wh_hours[d] = round(energy, 3)
                    #wh_days
                    d = datetime.datetime(timestamp.year, timestamp.month, timestamp.day)
                    if d in self.wh_days:
                        self.wh_days[d] += round(energy, 3)
                    else:
                        self.wh_days[d] = round(energy, 3)
            except Exception as err:
                _LOGGER.error(traceback.format_exc())

            self.savedata["wh_days"] = self.wh_days
            self.savedata["wh_hours"] = self.wh_hours
            self.savedata["energy_production_forecast_today"] = round(self.energy_production_today/1000, 3)
            self.savedata["sum_energy_production_remaining_today"] = round(self.sum_energy_production_remaining_today()/1000, 3)
            self.savedata["energy_production_forecast_tomorrow"] = round(self.energy_production_tomorrow/1000, 3)
            self.savedata["energy_this_hour"] = round(self.sum_energy_production(0)/1000, 3)
            self.savedata["energy_next_hour"] = round(self.sum_energy_production(1)/1000, 3)
            self.savedata["last_update"] = datetime.datetime.strptime(str(self.last_update), "%Y%m%d%H%M%S")
            self.savedata["solcast_api_poll_counter"] = bool(self.api_remaining > 0)

            apicounter = 0
            if _doData1 and _doData2:
                apicounter = 2
            elif _doData1 or _doData2:
                apicounter = 1

            if not _dontsave:
                try:
                    self.api_remaining -= apicounter

                    d = int(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
                    self.last_update = d

                    newlist = []
                    for forecast in self.savedata['forecasts']:
                        newlist.append({"pv_estimate": float(forecast["pv_estimate"]) / 1000.0,
                                        "period_end":forecast["period_end"].astimezone(timezone.utc).isoformat(), 
                                        "period": "PT30M"})

                    jsondata = json.dumps(newlist, indent=4, sort_keys=True, default=str)
                    encoded_forecasts = base64.urlsafe_b64encode(jsondata.encode()).decode()

                    data = {"apiremaining": self.api_remaining, "data": encoded_forecasts, "last_update": d}
                    self.hass.config_entries.async_update_entry(self.entry, data=data)
                except Exception as er:
                    _LOGGER.error(traceback.format_exc())

            return self.savedata

        except Exception as err:
            _LOGGER.error(traceback.format_exc())

        return None

    async def update_hass(self, *args):
        _LOGGER.debug("%s - Solcast API poll count reset to 50", self.logname)
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except Exception as err:
            raise UpdateFailed(err) from err
    
    async def _async_update_data(self) -> dict[str, str]:
        """Update Solcast data."""
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except Exception as err:
            raise UpdateFailed(err) from err
        
    def async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
        client = hass.data[DOMAIN][entry.unique_id]
        conf = {}

        for k in entry.data:
            conf[k] = entry.data[k]

        for k in entry.options:
            conf[k] = entry.options[k]
        
        client.updateConfig(conf)
        
        return True 

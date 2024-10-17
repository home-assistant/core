"""The mawaqit_prayer_times component."""

from collections.abc import Callable
from datetime import datetime, timedelta
import json
import logging
import os
import shutil
from typing import Any

from dateutil import parser as date_parser
from mawaqit.consts import BadCredentialsException
from requests.exceptions import ConnectionError as ConnError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
from homeassistant.util.dt import now as ha_now

from . import utils
from .const import (
    CONF_CALC_METHOD,
    DATA_UPDATED,
    DEFAULT_CALC_METHOD,
    DOMAIN,
    MAWAQIT_ALL_MOSQUES_NN,
    MAWAQIT_MY_MOSQUE_NN,
    MAWAQIT_PRAY_TIME,
    MAWAQIT_STORAGE_KEY,
    MAWAQIT_STORAGE_VERSION,
    UPDATE_TIME,
)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
file_path = f"{CURRENT_DIR}/data/mosq_list_data"

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


try:
    with open(file_path, encoding="utf-8") as text_file:
        data = json.load(text_file)

    # Accessing the CALC_METHODS object
    CALC_METHODS = data["CALC_METHODS"]
except FileNotFoundError:
    # First Run
    _LOGGER.warning("The file %s was not found", file_path)
    CALC_METHODS = []


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: {
                vol.Optional(CONF_CALC_METHOD, default=DEFAULT_CALC_METHOD): vol.In(
                    CALC_METHODS
                ),
            }
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


def is_date_parsing(date_str):
    """Check if the given string can be parsed into a date."""
    try:
        return bool(date_parser.parse(date_str))
    except ValueError:
        return False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import the Mawaqit Prayer component from config."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mawaqit Prayer Component."""

    hass.data.setdefault(DOMAIN, {})
    client = MawaqitPrayerClient(hass, config_entry)

    if not await client.async_setup():
        return False

    hass.data[DOMAIN] = client
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Mawaqit Prayer entry from config_entry."""

    if hass.data[DOMAIN].event_unsub:
        hass.data[DOMAIN].event_unsub()
    hass.data.pop(DOMAIN)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove Mawaqit Prayer entry from config_entry."""
    _LOGGER.debug("Started clearing data folder")
    dir_path = f"{CURRENT_DIR}/data"
    try:
        shutil.rmtree(dir_path)
    except OSError as e:
        _LOGGER.error("Error: %s : %s", dir_path, e.strerror)

    dir_path = f"{CURRENT_DIR}/__pycache__"
    try:
        shutil.rmtree(dir_path)
    except OSError as e:
        _LOGGER.error("Error: %s : %s", dir_path, e.strerror)

    store: Store = Store(hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY)
    await utils.cleare_storage_entry(store, MAWAQIT_MY_MOSQUE_NN)
    await utils.cleare_storage_entry(store, MAWAQIT_ALL_MOSQUES_NN)
    await utils.cleare_storage_entry(store, MAWAQIT_PRAY_TIME)
    # after adding MAWAQIT_MOSQ_LIST_DATA to storage we need to clear it here

    _LOGGER.debug("Finished clearing data folder")


class MawaqitPrayerClient:
    """Mawaqit Prayer Client Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Mawaqit Prayer client."""
        self.hass = hass
        self.config_entry = config_entry
        self.prayer_times_info: dict[str, Any] = {}
        self.available = True
        self.event_unsub = None
        self.store: Store = Store(
            self.hass, MAWAQIT_STORAGE_VERSION, MAWAQIT_STORAGE_KEY
        )

        self.cancel_events_next_salat: list[
            Callable[[], None]
        ] = []  # TODO verify if it should not be None instead # pylint: disable=fixme

    @property
    def calc_method(self):
        """Return the calculation method."""
        return self.config_entry.options[CONF_CALC_METHOD]

    async def get_new_prayer_times(self):
        """Fetch prayer times for today."""
        mawaqit_login = self.config_entry.data.get("username")  # noqa: F841
        mawaqit_password = self.config_entry.data.get("password")  # noqa: F841
        mawaqit_latitude = self.config_entry.data.get("latitude")  # noqa: F841
        mawaqit_longitude = self.config_entry.data.get("longitude")  # noqa: F841

        mosque = self.config_entry.options.get("calculation_method")  # noqa: F841

        name_servers = []  # noqa: F841
        uuid_servers = []  # noqa: F841
        # TODO check if we should keep this or no  # pylint: disable=fixme
        CALC_METHODS.clear()  # changed due to W0621 with pylint and F841 with Ruff

        # TODO reload files here from API # pylint: disable=fixme
        # We get the prayer times of the year from pray_time.txt
        await utils.update_my_mosque_data_files(
            self.hass, CURRENT_DIR, store=self.store
        )

        data_pray_time = await utils.read_pray_time(self.store)

        # data_pray_time = content
        calendar = data_pray_time["calendar"]

        # Then, we get the prayer times of the day into this file

        today = ha_now()
        index_month = today.month - 1
        month_times = calendar[index_month]  # Calendar of the month

        index_day = today.day
        day_times = month_times[str(index_day)]  # Today's times

        try:
            day_times_tomorrow = month_times[str(index_day + 1)]
        except KeyError:
            # If index_day + 1 == 32 (or 31) and the month contains only 31 (or 30) days
            # We take the first day of the following month (reset 0 if we're in december)
            if index_month == 11:
                index_next_month = 0
            else:
                index_next_month = index_month + 1
            day_times_tomorrow = calendar[index_next_month]["1"]

        now = today.time().strftime("%H:%M")

        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        today = today.strftime("%Y-%m-%d")

        ordered_prayer_names = ["Fajr", "Shurouq", "Dhuhr", "Asr", "Maghrib", "Isha"]
        prayers = []
        res = {}

        for i, prayer_name in enumerate(ordered_prayer_names):
            if datetime.strptime(day_times[i], "%H:%M") < datetime.strptime(
                now, "%H:%M"
            ):
                res[prayer_name] = day_times_tomorrow[i]
                pray = tomorrow + " " + day_times_tomorrow[i] + ":00"
            else:
                res[prayer_name] = day_times[i]
                pray = today + " " + day_times[i] + ":00"

            # # We never take in account shurouq in the calculation of next_salat
            if prayer_name == "Shurouq":
                pray = tomorrow + " " + "23:59:59"

            prayers.append(pray)

        # Then the next prayer is the nearest prayer time, so the min of the prayers list
        next_prayer = min(prayers)
        res["Next Salat Time"] = next_prayer.split(" ", 1)[1].rsplit(":", 1)[0]
        next_prayer_index = prayers.index(next_prayer)

        res["Next Salat Name"] = ordered_prayer_names[next_prayer_index]

        countdown_next_prayer = 15
        # 15 minutes Before Next Prayer
        res["Next Salat Preparation"] = (
            (
                datetime.strptime(next_prayer, "%Y-%m-%d %H:%M:%S")
                - timedelta(minutes=countdown_next_prayer)
            )
            .strftime("%Y-%m-%d %H:%M:%S")
            .split(" ", 1)[1]
            .rsplit(":", 1)[0]
        )

        # if Jumu'a is set as Dhuhr, then Jumu'a time is the same as Friday's Dhuhr time
        if data_pray_time["jumuaAsDuhr"]:
            # Then, Jumu'a time should be the Dhuhr time of the next Friday
            today = ha_now().today()
            # We get the next Friday
            next_friday = today + timedelta((4 - today.weekday() + 7) % 7)
            # We get the next Friday's Dhuhr time from the calendar
            next_friday_dhuhr = calendar[next_friday.month - 1][str(next_friday.day)][2]
            res["Jumua"] = next_friday_dhuhr

        # If jumu'a is set as a specific time, then we use that time
        elif data_pray_time["jumua"] is not None:
            res["Jumua"] = data_pray_time["jumua"]

        # if mosque has only one jumu'a, then 'Jumua 2' can be None.
        if data_pray_time["jumua2"] is not None:
            res["Jumua 2"] = data_pray_time["jumua2"]

        res["Mosque_label"] = data_pray_time["label"]
        res["Mosque_localisation"] = data_pray_time["localisation"]
        res["Mosque_url"] = data_pray_time["url"]
        res["Mosque_image"] = data_pray_time["image"]

        # We store the prayer times of the day in HH:MM format.
        prayers = [datetime.strptime(prayer, "%H:%M") for prayer in day_times]
        del prayers[1]  # Because there's no iqama for shurouq.

        # The Iqama countdown from Adhan is stored in pray_time.txt as well.
        iqamaCalendar = data_pray_time["iqamaCalendar"]
        iqamas = iqamaCalendar[index_month][str(index_day)]  # Today's iqama times.

        # We store the iqama times of the day in HH:MM format.
        iqama_times = []

        for prayer, iqama in zip(prayers, iqamas, strict=False):
            # The iqama can be either stored as a minutes countdown starting by a '+', or as a fixed time (HH:MM).
            if "+" in iqama:
                iqama = int(iqama.replace("+", ""))
                iqama_times.append(
                    (prayer + timedelta(minutes=iqama)).strftime("%H:%M")
                )
            elif ":" in iqama:
                iqama_times.append(iqama)
            else:
                # if there's a bug, we just append the prayer time for now.
                iqama.append(prayer)

        iqama_names = [
            "Fajr Iqama",
            "Dhuhr Iqama",
            "Asr Iqama",
            "Maghrib Iqama",
            "Isha Iqama",
        ]

        res1 = {iqama_names[i]: iqama_times[i] for i in range(len(iqama_names))}

        _LOGGER.debug("[;] get_new_prayer_times results : %s", {**res, **res1})
        return {**res, **res1}

    async def async_update_next_salat_sensor(self, *_):
        """Update the next salat sensor with the upcoming prayer time."""
        salat_before_update = self.prayer_times_info["Next Salat Name"]
        prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

        _LOGGER.info(
            "[;] [async_update_next_salat_sensor] salat_before_update : %s",
            salat_before_update,
        )

        if salat_before_update != "Isha":  # We just retrieve the next salat of the day.
            index = prayers.index(salat_before_update) + 1
            self.prayer_times_info["Next Salat Name"] = prayers[index]
            self.prayer_times_info["Next Salat Time"] = self.prayer_times_info[
                prayers[index]
            ]

        else:  # We retrieve the next Fajr (more calculations).
            data_pray_time = await utils.read_pray_time(self.store)
            calendar = data_pray_time["calendar"]

            today = ha_now().today()
            index_month = today.month - 1
            month_times = calendar[index_month]

            maghrib_hour = self.prayer_times_info["Maghrib"]
            maghrib_hour = maghrib_hour.strftime("%H:%M")

            # isha + 1 minute because this function is launched 1 minute after 'Isha, (useful only if 'Isha is at 11:59 PM)
            isha_hour = self.prayer_times_info["Isha"] + timedelta(minutes=1)
            isha_hour = isha_hour.strftime("%H:%M")

            # If 'Isha is before 12 AM (Maghrib hour < 'Isha hour), we need to get the next day's Fajr.
            # Else, we get the current day's Fajr.
            if maghrib_hour < isha_hour:
                index_day = today.day + 1
            else:
                index_day = today.day

            try:
                day_times = month_times[str(index_day)]
            except KeyError:
                # If index_day + 1 == 32 (or 31) and the month contains only 31 (or 30) days
                # We take the first day of the following month (reset 0 if we're in december)
                if index_month == 11:
                    index_next_month = 0
                else:
                    index_next_month = index_month + 1
                day_times = calendar[index_next_month]["1"]
            fajr_hour = day_times[0]

            self.prayer_times_info["Next Salat Name"] = "Fajr"
            self.prayer_times_info["Next Salat Time"] = dt_util.parse_datetime(
                f"{today.year}-{today.month}-{index_day} {fajr_hour}:00"
            )

        countdown_next_prayer = 15
        if self.prayer_times_info["Next Salat Time"] is not None:
            self.prayer_times_info["Next Salat Preparation"] = self.prayer_times_info[
                "Next Salat Time"
            ] - timedelta(minutes=countdown_next_prayer)
        else:
            # TODO check if this is correct # pylint: disable=fixme
            self.prayer_times_info["Next Salat Preparation"] = None

        _LOGGER.debug("Next salat info updated, updating sensors")
        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_update(self, *_):
        """Update sensors with new prayer times."""
        try:
            # should we use self.hass.async_add_executor_job to wrap get_new_prayer_times?
            prayer_times = await self.get_new_prayer_times()
            self.available = True
        except (BadCredentialsException, ConnError):
            self.available = False
            _LOGGER.debug("Error retrieving prayer times")
            async_call_later(self.hass, 60, self.async_update)
            return

        _LOGGER.debug("[;] prayer_times : %s", prayer_times)
        _LOGGER.debug("[;] ha_now() times : %s", ha_now().time())
        _LOGGER.debug("[;] ha_now() date : %s", ha_now().date())

        for prayer, time in prayer_times.items():
            tomorrow = (ha_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
            today = ha_now().date().strftime("%Y-%m-%d")

            now = ha_now().time().strftime("%H:%M")
            _LOGGER.debug("[;] is_date_parsing(%s) : %s ", time, is_date_parsing(time))
            if is_date_parsing(time):
                if datetime.strptime(time, "%H:%M") < datetime.strptime(now, "%H:%M"):
                    pray = tomorrow
                else:
                    pray = today

                if prayer in ("Jumua", "Jumua 2"):
                    # We convert the date to datetime to be able to do calculations on it.
                    pray_date = datetime.strptime(pray, "%Y-%m-%d")
                    # The calculation below allows to add the number of days necessary to arrive at the next Friday.
                    pray_date += timedelta(days=(4 - pray_date.weekday() + 7) % 7)
                    # We convert the date to string to be able to put it in the dictionary.
                    pray = pray_date.strftime("%Y-%m-%d")

                self.prayer_times_info[prayer] = dt_util.parse_datetime(
                    f"{pray} {time}"
                )
                _LOGGER.info(
                    "[;] [async_update] self.prayer_times_info[prayer] : %s",
                    self.prayer_times_info[prayer],
                )
            else:
                self.prayer_times_info[prayer] = time

        # We schedule updates for next_salat_time and next_salat_name at each prayer time + 1 minute.
        prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        prayer_times = [self.prayer_times_info[prayer] for prayer in prayers]

        _LOGGER.info("[;] [async_update] prayer_times : %s", prayer_times)

        # We cancel the previous scheduled updates (if there is any) to avoid multiple updates for the same prayer.
        try:
            for cancel_event in self.cancel_events_next_salat:
                cancel_event()
        except AttributeError:
            pass

        self.cancel_events_next_salat = []

        for prayer in prayer_times:
            next_update_at = prayer + timedelta(minutes=1)
            cancel_event = async_track_point_in_time(
                self.hass, self.async_update_next_salat_sensor, next_update_at
            )
            self.cancel_events_next_salat.append(cancel_event)

        _LOGGER.debug(
            "[;] [async_update] self.prayer_times_info : %s", self.prayer_times_info
        )

        _LOGGER.debug("New prayer times retrieved. Updating sensors")
        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_setup(self):
        """Set up the Mawaqit prayer client."""

        await self.async_add_options()

        try:
            await self.get_new_prayer_times()
            # should we use self.hass.async_add_executor_job to wrap get_new_prayer_times?
        except (BadCredentialsException, ConnError) as err:
            raise ConfigEntryNotReady from err

        await self.async_update()
        self.config_entry.add_update_listener(self.async_options_updated)

        # We update time prayers every day.
        h, m, s = UPDATE_TIME
        async_track_time_change(
            self.hass, self.async_update, hour=h, minute=m, second=s
        )

        return True

    async def async_add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            data_config_entry = dict(self.config_entry.data)
            calc_method = data_config_entry.pop(CONF_CALC_METHOD, DEFAULT_CALC_METHOD)

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=data_config_entry,
                options={CONF_CALC_METHOD: calc_method},
            )

    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
        """Triggered by config entry options updates."""
        if hass.data[DOMAIN].event_unsub:
            hass.data[DOMAIN].event_unsub()
        await hass.data[DOMAIN].async_update()

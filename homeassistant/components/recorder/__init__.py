"""Support for recording details."""
import asyncio
from collections import namedtuple
import concurrent.futures
from datetime import datetime
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, event as sqlalchemy_event, exc, select
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED,
    MATCH_ALL,
)
from homeassistant.core import CoreState, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from . import migration, purge
from .const import DATA_INSTANCE
from .models import Base, Events, RecorderRuns, States
from .util import session_scope

_LOGGER = logging.getLogger(__name__)

DOMAIN = "recorder"

SERVICE_PURGE = "purge"

ATTR_KEEP_DAYS = "keep_days"
ATTR_REPACK = "repack"

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
    }
)

DEFAULT_URL = "sqlite:///{hass_config_path}"
DEFAULT_DB_FILE = "home-assistant_v2.db"
DEFAULT_DB_MAX_RETRIES = 10
DEFAULT_DB_RETRY_WAIT = 3
KEEPALIVE_TIME = 30

CONF_AUTO_PURGE = "auto_purge"
CONF_DB_URL = "db_url"
CONF_DB_MAX_RETRIES = "db_max_retries"
CONF_DB_RETRY_WAIT = "db_retry_wait"
CONF_PURGE_KEEP_DAYS = "purge_keep_days"
CONF_PURGE_INTERVAL = "purge_interval"
CONF_EVENT_TYPES = "event_types"
CONF_COMMIT_INTERVAL = "commit_interval"

FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE, default={}): vol.Schema(
            {
                vol.Optional(CONF_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_ENTITIES): cv.entity_ids,
                vol.Optional(CONF_EVENT_TYPES): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
        vol.Optional(CONF_INCLUDE, default={}): vol.Schema(
            {
                vol.Optional(CONF_DOMAINS): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_ENTITIES): cv.entity_ids,
            }
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=dict): vol.All(
            cv.deprecated(CONF_PURGE_INTERVAL),
            FILTER_SCHEMA.extend(
                {
                    vol.Optional(CONF_AUTO_PURGE, default=True): cv.boolean,
                    vol.Optional(CONF_PURGE_KEEP_DAYS, default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Optional(CONF_PURGE_INTERVAL, default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Optional(CONF_DB_URL): cv.string,
                    vol.Optional(CONF_COMMIT_INTERVAL, default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Optional(
                        CONF_DB_MAX_RETRIES, default=DEFAULT_DB_MAX_RETRIES
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_DB_RETRY_WAIT, default=DEFAULT_DB_RETRY_WAIT
                    ): cv.positive_int,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def run_information(hass, point_in_time: Optional[datetime] = None):
    """Return information about current run.

    There is also the run that covers point_in_time.
    """
    ins = hass.data[DATA_INSTANCE]

    recorder_runs = RecorderRuns
    if point_in_time is None or point_in_time > ins.recording_start:
        return ins.run_info

    with session_scope(hass=hass) as session:
        res = (
            session.query(recorder_runs)
            .filter(
                (recorder_runs.start < point_in_time)
                & (recorder_runs.end > point_in_time)
            )
            .first()
        )
        if res:
            session.expunge(res)
        return res


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the recorder."""
    conf = config[DOMAIN]
    auto_purge = conf[CONF_AUTO_PURGE]
    keep_days = conf[CONF_PURGE_KEEP_DAYS]
    commit_interval = conf[CONF_COMMIT_INTERVAL]
    db_max_retries = conf[CONF_DB_MAX_RETRIES]
    db_retry_wait = conf[CONF_DB_RETRY_WAIT]

    # db_url = conf.get(CONF_DB_URL, None)
    # if not db_url:
    #     db_url = DEFAULT_URL.format(hass_config_path=hass.config.path(DEFAULT_DB_FILE))
    # AIS dom fix - get recorder config from file
    try:
        import json
        from homeassistant.components import ais_files
        import homeassistant.components.ais_dom.ais_global as ais_global

        with open(ais_files.G_DB_SETTINGS_INFO_FILE) as json_file:
            db_settings = json.load(json_file)
            ais_global.G_DB_SETTINGS_INFO = db_settings
        db_url = db_settings["dbUrl"]
        if db_url == "sqlite:///:memory:":
            keep_days = 2
            purge_interval = 1
            commit_interval = 60
            db_max_retries = 10
            db_retry_wait = 3
        else:
            if db_url.startswith("sqlite://///"):
                # DB in file
                from homeassistant.components import ais_usb

                if ais_usb.is_usb_url_valid_external_drive(db_url) is not True:
                    _LOGGER.error(
                        "Invalid external drive: %s selected for recording! ", db_url
                    )
                    return False
            keep_days = 10
            if "dbKeepDays" in db_settings:
                keep_days = int(db_settings["dbKeepDays"])
            purge_interval = 1
            commit_interval = 60
            db_max_retries = 10
            db_retry_wait = 3
        include = conf.get(CONF_INCLUDE, {})
    except Exception:
        # enable recorder in memory
        db_url = "sqlite:///:memory:"
        keep_days = 1
        purge_interval = 1
        commit_interval = 60
        db_max_retries = 10
        db_retry_wait = 3

    include = conf.get(CONF_INCLUDE, {})
    exclude = {
        "domains": [
            "ais_ai_service",
            "ais_amplifier_service",
            "ais_audiobooks_service",
            "ais_bookmarks",
            "ais_cloud",
            "ais_device_search_mqtt",
            "ais_dom",
            "ais_dom_device",
            "ais_drives_service",
            "ais_exo_player",
            "ais_files",
            "ais_gm_service",
            "ais_google_home",
            "ais_help",
            "ais_host",
            "ais_ingress",
            "ais_knowledge_service",
            "ais_mdns",
            "ais_qrcode",
            "ais_shell_command",
            "ais_spotify_service",
            "ais_updater",
            "ais_usb",
            "ais_wifi_service",
            "ais_yt_service",
            "media_player",
            "group",
        ],
        "entities": [
            "sun.sun",
            "sensor.nextsunrise",
            "sensor.nextsunset",
            "sensor.date",
            "sensor.time",
            "automation.ais_ask_the_question",
            "automation.ais_asystent_domowy_witamy",
            "automation.ais_change_audio_to_mono",
            "automation.ais_change_equalizer_mode",
            "automation.ais_change_player_speed",
            "automation.ais_change_remote_web_access",
            "automation.ais_check_wifi_connection",
            "automation.ais_discovery_info_to_dom_devices",
            "automation.ais_execute_process_command_web_hook",
            "automation.ais_flush_logs",
            "automation.ais_get_books",
            "automation.ais_get_podcast_names",
            "automation.ais_get_radio_names",
            "automation.ais_get_rss_help_items_for_selected_topic",
            "automation.ais_get_rss_news_channels",
            "automation.ais_get_rss_news_items",
            "automation.ais_ifttt_info",
            "automation.ais_search_spotify_tracks",
            "automation.ais_search_youtube_tracks",
            "automation.ais_select_bookmark_to_play",
            "automation.ais_select_device_to_add",
            "automation.ais_set_wifi_config_for_devices",
            "binary_sensor.ais_remote_button",
            "group.ais_add_iot_device",
            "group.ais_bookmarks",
            "group.ais_favorites",
            "group.ais_pogoda",
            "group.ais_rss_help_remote",
            "group.ais_rss_news_remote",
            "group.ais_tts_configuration",
            "group.all_ais_automations",
            "group.all_ais_cameras",
            "group.all_ais_climates",
            "group.all_ais_covers",
            "group.all_ais_devices",
            "group.all_ais_fans",
            "group.all_ais_lights",
            "group.all_ais_locks",
            "group.all_ais_persons",
            "group.all_ais_scenes",
            "group.all_ais_sensors",
            "group.all_ais_switches",
            "group.all_ais_vacuums",
            "input_boolean.ais_audio_mono",
            "input_boolean.ais_auto_update",
            "input_boolean.ais_quiet_mode",
            "input_boolean.ais_remote_access",
            "input_datetime.ais_quiet_mode_start",
            "input_datetime.ais_quiet_mode_stop",
            "input_select.ais_android_wifi_network",
            "input_select.ais_iot_devices_in_network",
            "input_select.ais_music_service",
            "input_select.ais_rss_help_topic",
            "input_select.ais_system_logs_level",
            "input_select.ais_usb_flash_drives",
            "input_text.ais_android_wifi_password",
            "input_text.ais_iot_device_name",
            "input_text.ais_iot_device_wifi_password",
            "input_text.ais_knowledge_query",
            "input_text.ais_music_query",
            "input_text.ais_spotify_query",
            "script.ais_add_item_to_bookmarks",
            "script.ais_add_item_to_favorites",
            "script.ais_button_click",
            "script.ais_cloud_sync",
            "script.ais_connect_android_wifi_network",
            "script.ais_connect_iot_device_to_network",
            "script.ais_restart_system",
            "script.ais_scan_android_wifi_network",
            "script.ais_scan_iot_devices_in_network",
            "script.ais_scan_network_devices",
            "script.ais_stop_system",
            "script.ais_update_system",
            "sensor.ais_all_files",
            "sensor.ais_connect_iot_device_info",
            "sensor.ais_db_connection_info",
            "sensor.ais_dom_mqtt_rf_sensor",
            "sensor.ais_drives",
            "sensor.ais_gallery_img",
            "sensor.ais_logs_settings_info",
            "sensor.ais_player_mode",
            "sensor.ais_secure_android_id_dom",
            "sensor.ais_wifi_service_current_network_info",
            "sensor.aisbackupinfo",
            "sensor.aisbookmarkslist",
            "sensor.aisfavoriteslist",
            "sensor.aisknowledgeanswer",
            "sensor.aisrsshelptext",
            "timer.ais_dom_pin",
            "input_select.book_autor",
            "group.audiobooks_player",
            "input_select.podcast_type",
            "input_select.radio_type",
            "sensor.dayofyear",
            "sensor.weekofyear",
            "sensor.daytodisplay",
            "group.day_info",
            "group.local_audio",
            "group.radio_player",
            "group.podcast_player",
            "group.music_player",
            "group.internet_status",
            "group.audio_player",
            "group.dom_system_version",
            "sensor.radiolist",
            "sensor.podcastnamelist",
            "sensor.youtubelist",
            "sensor.spotifysearchlist",
            "sensor.spotifylist",
            "sensor.rssnewslist",
            "input_select.rss_news_category",
            "input_select.rss_news_channel",
            "sensor.selected_entity",
            "sensor.wersja_kordynatora",
            "sensor.status_serwisu_zigbee2mqtt",
            "sensor.gate_pairing_pin",
            "persistent_notification.config_entry_discovery",
            "sensor.audiobookschapterslist",
            "automation.zigbee_tryb_parowania",
            "automation.zigbee_wylaczenie_trybu_parowania",
            "input_number.assistant_rate",
            "input_number.media_player_speed",
            "timer.ais_dom_pin_join",
            "media_player.wbudowany_glosnik",
            "input_number.assistant_tone",
            "timer.zigbee_permit_join",
            "input_select.book_name",
            "sensor.podcastlist",
            "sensor.audiobookslist",
            "sensor.rssnewstext",
            "sensor.wersja_zigbee2mqtt",
            "switch.zigbee_tryb_parowania",
            "input_select.book_chapter",
            "input_select.assistant_voice",
            "sensor.network_devices_info_value",
            "input_text.zigbee2mqtt_old_name",
            "input_text.zigbee2mqtt_new_name",
            "sensor.zigbee2mqtt_networkmap",
            "input_text.zigbee2mqtt_remove",
            "input_select.media_player_sound_mode",
            "weather.openweathermap",
            "binary_sensor.updater",
            "weather.dom",
            "camera.remote_access",
            "binary_sensor.selected_entity",
            # "sensor.dark_sky_daily_summary",
            # "sensor.dark_sky_hourly_summary",
            # "sensor.dark_sky_visibility",
            # "sensor.dark_sky_visibility_0d",
            # "sensor.dark_sky_apparent_temperature",
            # "sensor.dark_sky_cloud_coverage",
            # "sensor.dark_sky_cloud_coverage_0d",
            # "sensor.dark_sky_humidity",
            # "sensor.dark_sky_humidity_0d",
            # "sensor.dark_sky_pressure",
            # "sensor.dark_sky_pressure_0d",
            # "sensor.dark_sky_temperature",
            # "sensor.dark_sky_wind_speed",
            # "sensor.dark_sky_wind_speed_0d",
        ],
    }

    instance = hass.data[DATA_INSTANCE] = Recorder(
        hass=hass,
        auto_purge=auto_purge,
        keep_days=keep_days,
        commit_interval=commit_interval,
        uri=db_url,
        db_max_retries=db_max_retries,
        db_retry_wait=db_retry_wait,
        include=include,
        exclude=exclude,
    )
    instance.async_initialize()
    instance.start()

    async def async_handle_purge_service(service):
        """Handle calls to the purge service."""
        instance.do_adhoc_purge(**service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_PURGE, async_handle_purge_service, schema=SERVICE_PURGE_SCHEMA
    )

    return await instance.async_db_ready


PurgeTask = namedtuple("PurgeTask", ["keep_days", "repack"])


class Recorder(threading.Thread):
    """A threaded recorder class."""

    def __init__(
        self,
        hass: HomeAssistant,
        auto_purge: bool,
        keep_days: int,
        commit_interval: int,
        uri: str,
        db_max_retries: int,
        db_retry_wait: int,
        include: Dict,
        exclude: Dict,
    ) -> None:
        """Initialize the recorder."""
        threading.Thread.__init__(self, name="Recorder")

        self.hass = hass
        self.auto_purge = auto_purge
        self.keep_days = keep_days
        self.commit_interval = commit_interval
        self.queue: Any = queue.Queue()
        self.recording_start = dt_util.utcnow()
        self.db_url = uri
        self.db_max_retries = db_max_retries
        self.db_retry_wait = db_retry_wait
        self.async_db_ready = asyncio.Future()
        self.engine: Any = None
        self.run_info: Any = None

        self.entity_filter = generate_filter(
            include.get(CONF_DOMAINS, []),
            include.get(CONF_ENTITIES, []),
            exclude.get(CONF_DOMAINS, []),
            exclude.get(CONF_ENTITIES, []),
        )
        self.exclude_t = exclude.get(CONF_EVENT_TYPES, [])

        self._timechanges_seen = 0
        self._keepalive_count = 0
        self.event_session = None
        self.get_session = None

    @callback
    def async_initialize(self):
        """Initialize the recorder."""
        self.hass.bus.async_listen(MATCH_ALL, self.event_listener)

    def do_adhoc_purge(self, **kwargs):
        """Trigger an adhoc purge retaining keep_days worth of data."""
        keep_days = kwargs.get(ATTR_KEEP_DAYS, self.keep_days)
        repack = kwargs.get(ATTR_REPACK)

        self.queue.put(PurgeTask(keep_days, repack))

    def run(self):
        """Start processing events to save."""
        tries = 1
        connected = False

        while not connected and tries <= self.db_max_retries:
            if tries != 1:
                time.sleep(self.db_retry_wait)
            try:
                self._setup_connection()
                migration.migrate_schema(self)
                self._setup_run()
                connected = True
                _LOGGER.debug("Connected to recorder database")
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Error during connection setup: %s (retrying in %s seconds)",
                    err,
                    self.db_retry_wait,
                )
                tries += 1

        if not connected:

            @callback
            def connection_failed():
                """Connect failed tasks."""
                self.async_db_ready.set_result(False)
                persistent_notification.async_create(
                    self.hass,
                    "The recorder could not start, please check the log",
                    "Recorder",
                )

            self.hass.add_job(connection_failed)
            return

        shutdown_task = object()
        hass_started = concurrent.futures.Future()

        @callback
        def register():
            """Post connection initialize."""
            self.async_db_ready.set_result(True)

            def shutdown(event):
                """Shut down the Recorder."""
                print("Shut down the Recorder.")
                if not hass_started.done():
                    hass_started.set_result(shutdown_task)
                self.queue.put(None)
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
            self.hass.bus.async_listen("ais_stop_recorder_event", shutdown)

            if self.hass.state == CoreState.running:
                hass_started.set_result(None)
            else:

                @callback
                def notify_hass_started(event):
                    """Notify that hass has started."""
                    hass_started.set_result(None)

                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_START, notify_hass_started
                )

        self.hass.add_job(register)
        result = hass_started.result()

        # If shutdown happened before Home Assistant finished starting
        if result is shutdown_task:
            return

        # Start periodic purge
        if self.auto_purge:

            @callback
            def async_purge(now):
                """Trigger the purge."""
                self.queue.put(PurgeTask(self.keep_days, repack=False))

            # Purge every night at 4:12am
            self.hass.helpers.event.track_time_change(
                async_purge, hour=4, minute=12, second=0
            )

        self.event_session = self.get_session()
        # Use a session for the event read loop
        # with a commit every time the event time
        # has changed.  This reduces the disk io.
        while True:
            event = self.queue.get()
            if event is None:
                self._close_run()
                self._close_connection()
                self.queue.task_done()
                return
            if isinstance(event, PurgeTask):
                purge.purge_old_data(self, event.keep_days, event.repack)
                self.queue.task_done()
                continue
            if event.event_type == EVENT_TIME_CHANGED:
                self.queue.task_done()
                self._keepalive_count += 1
                if self._keepalive_count >= KEEPALIVE_TIME:
                    self._keepalive_count = 0
                    self._send_keep_alive()
                if self.commit_interval:
                    self._timechanges_seen += 1
                    if self._timechanges_seen >= self.commit_interval:
                        self._timechanges_seen = 0
                        self._commit_event_session_or_retry()
                continue
            if event.event_type in self.exclude_t:
                self.queue.task_done()
                continue

            entity_id = event.data.get(ATTR_ENTITY_ID)
            if entity_id is not None:
                if not self.entity_filter(entity_id):
                    self.queue.task_done()
                    continue

            try:
                dbevent = Events.from_event(event)
                self.event_session.add(dbevent)
                self.event_session.flush()
            except (TypeError, ValueError):
                _LOGGER.warning("Event is not JSON serializable: %s", event)
            except Exception as err:  # pylint: disable=broad-except
                # Must catch the exception to prevent the loop from collapsing
                _LOGGER.error("Error adding event: %s", err)

            if dbevent and event.event_type == EVENT_STATE_CHANGED:
                try:
                    dbstate = States.from_event(event)
                    dbstate.event_id = dbevent.event_id
                    self.event_session.add(dbstate)
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        "State is not JSON serializable: %s",
                        event.data.get("new_state"),
                    )
                except Exception as err:  # pylint: disable=broad-except
                    # Must catch the exception to prevent the loop from collapsing
                    _LOGGER.exception("Error adding state change: %s", err)

            # If they do not have a commit interval
            # than we commit right away
            if not self.commit_interval:
                self._commit_event_session_or_retry()
            self.queue.task_done()

    def _send_keep_alive(self):
        try:
            _LOGGER.debug("Sending keepalive")
            self.event_session.connection().scalar(select([1]))
            return
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.error("Error in database connectivity during keepalive: %s.", err)
            self._reopen_event_session()

    def _commit_event_session_or_retry(self):
        tries = 1
        while tries <= self.db_max_retries:
            if tries != 1:
                time.sleep(self.db_retry_wait)

            try:
                self._commit_event_session()
                return
            except (exc.InternalError, exc.OperationalError) as err:
                if err.connection_invalidated:
                    _LOGGER.error(
                        "Database connection invalidated: %s. "
                        "(retrying in %s seconds)",
                        err,
                        self.db_retry_wait,
                    )
                else:
                    _LOGGER.error(
                        "Error in database connectivity during commit: %s. "
                        "(retrying in %s seconds)",
                        err,
                        self.db_retry_wait,
                    )
                tries += 1

            except Exception as err:  # pylint: disable=broad-except
                # Must catch the exception to prevent the loop from collapsing
                _LOGGER.exception("Error saving events: %s", err)
                return

        _LOGGER.error(
            "Error in database update. Could not save " "after %d tries. Giving up",
            tries,
        )
        self._reopen_event_session()

    def _reopen_event_session(self):
        try:
            self.event_session.rollback()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while rolling back event session: %s", err)

        try:
            self.event_session.close()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while closing event session: %s", err)

        try:
            self.event_session = self.get_session()
        except Exception as err:  # pylint: disable=broad-except
            # Must catch the exception to prevent the loop from collapsing
            _LOGGER.exception("Error while creating new event session: %s", err)

    def _commit_event_session(self):
        try:
            self.event_session.commit()
        except Exception as err:
            _LOGGER.error("Error executing query: %s", err)
            self.event_session.rollback()
            raise

    @callback
    def event_listener(self, event):
        """Listen for new events and put them in the process queue."""
        self.queue.put(event)

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()

    def _setup_connection(self):
        """Ensure database is ready to fly."""
        kwargs = {}

        def setup_recorder_connection(dbapi_connection, connection_record):
            """Dbapi specific connection settings."""

            # We do not import sqlite3 here so mysql/other
            # users do not have to pay for it to be loaded in
            # memory
            if self.db_url.startswith("sqlite://"):
                old_isolation = dbapi_connection.isolation_level
                dbapi_connection.isolation_level = None
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
                dbapi_connection.isolation_level = old_isolation
            elif self.db_url.startswith("mysql"):
                cursor = dbapi_connection.cursor()
                cursor.execute("SET session wait_timeout=28800")
                cursor.close()

        if self.db_url == "sqlite://" or ":memory:" in self.db_url:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
            kwargs["pool_reset_on_return"] = None
        else:
            kwargs["echo"] = False

        if self.engine is not None:
            self.engine.dispose()

        self.engine = create_engine(self.db_url, **kwargs)

        sqlalchemy_event.listen(self.engine, "connect", setup_recorder_connection)

        Base.metadata.create_all(self.engine)
        self.get_session = scoped_session(sessionmaker(bind=self.engine))

    def _close_connection(self):
        """Close the connection."""
        self.engine.dispose()
        self.engine = None
        self.get_session = None

    def _setup_run(self):
        """Log the start of the current run."""
        with session_scope(session=self.get_session()) as session:
            for run in session.query(RecorderRuns).filter_by(end=None):
                run.closed_incorrect = True
                run.end = self.recording_start
                _LOGGER.warning(
                    "Ended unfinished session (id=%s from %s)", run.run_id, run.start
                )
                session.add(run)

            self.run_info = RecorderRuns(
                start=self.recording_start, created=dt_util.utcnow()
            )
            session.add(self.run_info)
            session.flush()
            session.expunge(self.run_info)

    def _close_run(self):
        """Save end time for current run."""
        if self.event_session is not None:
            self.run_info.end = dt_util.utcnow()
            self.event_session.add(self.run_info)
            self._commit_event_session_or_retry()
            self.event_session.close()

        self.run_info = None

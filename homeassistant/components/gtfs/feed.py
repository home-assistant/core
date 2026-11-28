"""Download, validate, and import GTFS feeds."""

import asyncio
import csv
from dataclasses import dataclass, field
import datetime as dt
from functools import partial
import io
from pathlib import Path
import threading
from typing import BinaryIO
import zipfile

from aiohttp import ClientError, ClientResponseError, ClientTimeout
import pygtfs
from pygtfs.gtfs_entities import Service, ServiceException, Stop
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .timetable import SERVICE_ADDED

# National feeds run to hundreds of megabytes, so only stalls are capped.
DOWNLOAD_TIMEOUT = ClientTimeout(total=None, sock_connect=30, sock_read=60)
CHUNK_SIZE = 2**20
_REQUIRED_FILES = frozenset(
    {"agency.txt", "routes.txt", "stop_times.txt", "stops.txt", "trips.txt"}
)
_CALENDAR_FILES = frozenset({"calendar.txt", "calendar_dates.txt"})
# A stop or platform; trips only stop at these.
LOCATION_TYPE_STOP = 0

type GtfsConfigEntry = ConfigEntry[GtfsFeed]


class CannotConnect(Exception):
    """The feed could not be downloaded."""


class InvalidFeed(Exception):
    """The download is not a usable GTFS feed."""


@dataclass
class GtfsFeed:
    """An imported GTFS schedule shared by an entry's calendars."""

    schedule: pygtfs.Schedule
    # The schedule's SQLAlchemy session is not thread-safe and calendars read
    # from executor threads.
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_service_date: dt.date | None = None


def feed_database_path(hass: HomeAssistant, database: str) -> Path:
    """Return the path of a config entry feed's SQLite database.

    The cache folder is left out of backups; setup downloads a missing feed again.
    """
    return Path(hass.config.cache_path(DOMAIN, database))


def _open_destination(destination: Path) -> BinaryIO:
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination.open("wb")


async def _async_download_feed(
    hass: HomeAssistant, url: str, destination: Path
) -> None:
    """Stream the feed at url to destination."""
    session = async_get_clientsession(hass)
    file = await hass.async_add_executor_job(_open_destination, destination)
    buffer = bytearray()
    try:
        async with session.get(url, timeout=DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                buffer += chunk
                if len(buffer) >= CHUNK_SIZE:
                    await hass.async_add_executor_job(file.write, buffer)
                    buffer.clear()
            if buffer:
                await hass.async_add_executor_job(file.write, buffer)
    # aiohttp error text includes the URL, which may hold credentials.
    except ClientResponseError as err:
        raise CannotConnect(f"HTTP status {err.status}") from err
    except (ClientError, TimeoutError) as err:
        raise CannotConnect(type(err).__name__) from err
    finally:
        await hass.async_add_executor_job(file.close)


async def async_fetch_feed(
    hass: HomeAssistant, url: str, db_path: Path, cancelled: threading.Event
) -> str | None:
    """Download, validate, and import the feed at url; return its agency name.

    Setting cancelled stops the import from leaving a database behind. It is
    set here when this task is cancelled, and by the caller when it removes the
    database, since the import thread outlives the cancelled task.
    """
    zip_path = db_path.with_suffix(".zip")
    try:
        await _async_download_feed(hass, url, zip_path)
        try:
            agency_name = await hass.async_add_executor_job(
                _validate_and_import, zip_path, db_path, cancelled
            )
        except asyncio.CancelledError:
            cancelled.set()
            raise
    finally:
        await hass.async_add_executor_job(partial(zip_path.unlink, missing_ok=True))
    return agency_name


def _validate_and_import(
    zip_path: Path, db_path: Path, cancelled: threading.Event
) -> str | None:
    agency_name = validate_feed(zip_path)
    import_feed(zip_path, db_path, cancelled)
    return agency_name


def validate_feed(zip_path: Path) -> str | None:
    """Check zip_path is a GTFS zip and return its first agency name."""
    if not zipfile.is_zipfile(zip_path):
        raise InvalidFeed("Not a zip file")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            if missing := _REQUIRED_FILES - names:
                raise InvalidFeed(f"Missing {', '.join(sorted(missing))}")
            if not names & _CALENDAR_FILES:
                raise InvalidFeed("Missing calendar.txt or calendar_dates.txt")
            with archive.open("agency.txt") as agency_file:
                row = next(
                    csv.DictReader(io.TextIOWrapper(agency_file, encoding="utf-8-sig")),
                    None,
                )
    except (
        zipfile.BadZipFile,
        NotImplementedError,
        RuntimeError,
        csv.Error,
        UnicodeDecodeError,
    ) as err:
        raise InvalidFeed(str(err)) from err
    if row is None:
        # pygtfs crashes on a header-only agency.txt.
        raise InvalidFeed("No agency in agency.txt")
    return row.get("agency_name") or None


def _append_feed(db_path: Path, zip_path: Path) -> None:
    schedule: pygtfs.Schedule | None = None
    try:
        schedule = pygtfs.Schedule(str(db_path))
        pygtfs.append_feed(schedule, str(zip_path))
    except (
        ValueError,
        KeyError,
        StopIteration,
        csv.Error,
        zipfile.BadZipFile,
        IntegrityError,
    ) as err:
        raise InvalidFeed(str(err)) from err
    finally:
        if schedule is not None:
            schedule.session.close()
            schedule.engine.dispose()


def import_feed(zip_path: Path, db_path: Path, cancelled: threading.Event) -> None:
    """Import zip_path into db_path, replacing it only on success.

    A cancelled import discards its result, even if cancelled after the swap.
    """
    tmp_path = db_path.with_name(f"{db_path.name}.tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        _append_feed(tmp_path, zip_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    if cancelled.is_set():
        tmp_path.unlink(missing_ok=True)
        return
    tmp_path.replace(db_path)
    if cancelled.is_set():
        db_path.unlink(missing_ok=True)


def open_feed(db_path: Path) -> GtfsFeed:
    """Open an imported feed for calendars reading from executor threads."""
    feed = GtfsFeed(pygtfs.Schedule(f"{db_path}?check_same_thread=False"))
    feed.last_service_date = _last_service_date(feed.schedule)
    return feed


def close_feed(feed: GtfsFeed) -> None:
    """Release the feed's database connections."""
    with feed.lock:
        feed.schedule.session.close()
        feed.schedule.engine.dispose()


def list_stops(feed: GtfsFeed) -> dict[str, str]:
    """Return stop names keyed by stop ID, ordered by name.

    Stations, entrances and other locations trips don't stop at are left out.
    """
    with feed.lock:
        stops = (
            feed.schedule.session.query(Stop.stop_id, Stop.stop_name)
            .filter(
                or_(
                    Stop.location_type.is_(None),
                    Stop.location_type == LOCATION_TYPE_STOP,
                )
            )
            .order_by(Stop.stop_name, Stop.stop_id)
            .all()
        )
    return {stop_id: stop_name or stop_id for stop_id, stop_name in stops}


def _last_service_date(schedule: pygtfs.Schedule) -> dt.date | None:
    """Return the last date the feed's calendars run any service."""
    session = schedule.session
    last_regular = session.query(func.max(Service.end_date)).scalar()
    last_added = (
        session.query(func.max(ServiceException.date))
        .filter(ServiceException.exception_type == SERVICE_ADDED)
        .scalar()
    )
    return max(filter(None, (last_regular, last_added)), default=None)

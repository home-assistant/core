"""Script to convert an old-format home-assistant.db to a new format one."""

import argparse
import os.path
import sqlite3
import sys

from datetime import datetime
from typing import Optional, List

import homeassistant.config as config_util
import homeassistant.util.dt as dt_util
# pylint: disable=unused-import
from homeassistant.components.recorder import REQUIREMENTS  # NOQA


def ts_to_dt(timestamp: Optional[float]) -> Optional[datetime]:
    """Turn a datetime into an integer for in the DB."""
    if timestamp is None:
        return None
    return dt_util.utc_from_timestamp(timestamp)


# Based on code at
# http://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
def print_progress(iteration: int, total: int, prefix: str = '',
                   suffix: str = '', decimals: int = 2,
                   bar_length: int = 68) -> None:
    """Print progress bar.

    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : number of decimals in percent complete (Int)
        barLength   - Optional  : character length of bar (Int)
    """
    filled_length = int(round(bar_length * iteration / float(total)))
    percents = round(100.00 * (iteration / float(total)), decimals)
    line = '#' * filled_length + '-' * (bar_length - filled_length)
    sys.stdout.write('%s [%s] %s%s %s\r' % (prefix, line,
                                            percents, '%', suffix))
    sys.stdout.flush()
    if iteration == total:
        print("\n")


def run(script_args: List) -> int:
    """Run the actual script."""
    # pylint: disable=invalid-name
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from homeassistant.components.recorder import models

    parser = argparse.ArgumentParser(
        description="Migrate legacy DB to SQLAlchemy format.")
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '-a', '--append',
        action='store_true',
        default=False,
        help="Append to existing new format SQLite database")
    parser.add_argument(
        '--uri',
        type=str,
        help="Connect to URI and import (implies --append)"
             "eg: mysql://localhost/homeassistant")
    parser.add_argument(
        '--script',
        choices=['db_migrator'])

    args = parser.parse_args()

    config_dir = os.path.join(os.getcwd(), args.config)  # type: str

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir != config_util.get_default_config_dir():
            print(('Fatal Error: Specified configuration directory does '
                   'not exist {} ').format(config_dir))
            return 1

    src_db = '{}/home-assistant.db'.format(config_dir)
    dst_db = '{}/home-assistant_v2.db'.format(config_dir)

    if not os.path.exists(src_db):
        print("Fatal Error: Old format database '{}' does not exist".format(
            src_db))
        return 1
    if not args.uri and (os.path.exists(dst_db) and not args.append):
        print("Fatal Error: New format database '{}' exists already - "
              "Remove it or use --append".format(dst_db))
        print("Note: --append must maintain an ID mapping and is much slower"
              "and requires sufficient memory to track all event IDs")
        return 1

    conn = sqlite3.connect(src_db)
    uri = args.uri or "sqlite:///{}".format(dst_db)

    engine = create_engine(uri, echo=False)
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    append = args.append or args.uri

    c = conn.cursor()
    c.execute("SELECT count(*) FROM recorder_runs")
    num_rows = c.fetchone()[0]
    print("Converting {} recorder_runs".format(num_rows))
    c.close()

    c = conn.cursor()
    n = 0
    for row in c.execute("SELECT * FROM recorder_runs"):  # type: ignore
        n += 1
        session.add(models.RecorderRuns(
            start=ts_to_dt(row[1]),
            end=ts_to_dt(row[2]),
            closed_incorrect=row[3],
            created=ts_to_dt(row[4])
        ))
        if n % 1000 == 0:
            session.commit()
            print_progress(n, num_rows)
    print_progress(n, num_rows)
    session.commit()
    c.close()

    c = conn.cursor()
    c.execute("SELECT count(*) FROM events")
    num_rows = c.fetchone()[0]
    print("Converting {} events".format(num_rows))
    c.close()

    id_mapping = {}

    c = conn.cursor()
    n = 0
    for row in c.execute("SELECT * FROM events"):  # type: ignore
        n += 1
        o = models.Events(
            event_type=row[1],
            event_data=row[2],
            origin=row[3],
            created=ts_to_dt(row[4]),
            time_fired=ts_to_dt(row[5]),
        )
        session.add(o)
        if append:
            session.flush()
            id_mapping[row[0]] = o.event_id
        if n % 1000 == 0:
            session.commit()
            print_progress(n, num_rows)
    print_progress(n, num_rows)
    session.commit()
    c.close()

    c = conn.cursor()
    c.execute("SELECT count(*) FROM states")
    num_rows = c.fetchone()[0]
    print("Converting {} states".format(num_rows))
    c.close()

    c = conn.cursor()
    n = 0
    for row in c.execute("SELECT * FROM states"):  # type: ignore
        n += 1
        session.add(models.States(
            entity_id=row[1],
            state=row[2],
            attributes=row[3],
            last_changed=ts_to_dt(row[4]),
            last_updated=ts_to_dt(row[5]),
            event_id=id_mapping.get(row[6], row[6]),
            domain=row[7]
        ))
        if n % 1000 == 0:
            session.commit()
            print_progress(n, num_rows)
    print_progress(n, num_rows)
    session.commit()
    c.close()
    return 0

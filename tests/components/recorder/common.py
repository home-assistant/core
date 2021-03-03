"""Common test utils for working with recorder."""

from datetime import timedelta

from homeassistant.components import recorder
from homeassistant.util import dt as dt_util

from tests.common import fire_time_changed


def wait_recording_done(hass):
    """Block till recording is done."""
    hass.block_till_done()
    trigger_db_commit(hass)
    hass.block_till_done()
    hass.data[recorder.DATA_INSTANCE].block_till_done()
    hass.block_till_done()


async def async_wait_recording_done(hass):
    """Block till recording is done."""
    await hass.loop.run_in_executor(None, wait_recording_done, hass)


def trigger_db_commit(hass):
    """Force the recorder to commit."""
    for _ in range(recorder.DEFAULT_COMMIT_INTERVAL):
        # We only commit on time change
        fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))


def corrupt_db_file(test_db_file):
    """Corrupt an sqlite3 database file."""
    with open(test_db_file, "w+") as fhandle:
        fhandle.seek(200)
        fhandle.write("I am a corrupt db" * 100)

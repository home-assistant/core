"""Common test utils for working with recorder."""
from datetime import timedelta

from homeassistant import core as ha
from homeassistant.components import recorder
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, fire_time_changed


def wait_recording_done(hass: HomeAssistantType) -> None:
    """Block till recording is done."""
    hass.block_till_done()
    trigger_db_commit(hass)
    hass.block_till_done()
    hass.data[recorder.DATA_INSTANCE].block_till_done()
    hass.block_till_done()


async def async_wait_recording_done_without_instance(hass: HomeAssistantType) -> None:
    """Block till recording is done."""
    await hass.loop.run_in_executor(None, wait_recording_done, hass)


def trigger_db_commit(hass: HomeAssistantType) -> None:
    """Force the recorder to commit."""
    for _ in range(recorder.DEFAULT_COMMIT_INTERVAL):
        # We only commit on time change
        fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))


async def async_wait_recording_done(
    hass: HomeAssistantType,
    instance: recorder.Recorder,
) -> None:
    """Async wait until recording is done."""
    await hass.async_block_till_done()
    async_trigger_db_commit(hass)
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass, instance)
    await hass.async_block_till_done()


@ha.callback
def async_trigger_db_commit(hass: HomeAssistantType) -> None:
    """Fore the recorder to commit. Async friendly."""
    for _ in range(recorder.DEFAULT_COMMIT_INTERVAL):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))


async def async_recorder_block_till_done(
    hass: HomeAssistantType,
    instance: recorder.Recorder,
) -> None:
    """Non blocking version of recorder.block_till_done()."""
    await hass.async_add_executor_job(instance.block_till_done)


def corrupt_db_file(test_db_file):
    """Corrupt an sqlite3 database file."""
    with open(test_db_file, "w+") as fhandle:
        fhandle.seek(200)
        fhandle.write("I am a corrupt db" * 100)

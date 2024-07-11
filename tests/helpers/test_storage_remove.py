"""Tests for the storage helper with minimal mocking."""

from datetime import timedelta
import os
from unittest.mock import patch

import py

from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_test_home_assistant


async def test_removing_while_delay_in_progress(tmpdir: py.path.local) -> None:
    """Test removing while delay in progress."""

    async with async_test_home_assistant() as hass:
        test_dir = await hass.async_add_executor_job(tmpdir.mkdir, "storage")

        with patch.object(storage, "STORAGE_DIR", test_dir):
            real_store = storage.Store(hass, 1, "remove_me")

            await real_store.async_save({"delay": "no"})

            assert await hass.async_add_executor_job(os.path.exists, real_store.path)

            real_store.async_delay_save(lambda: {"delay": "yes"}, 1)

            await real_store.async_remove()
            assert not await hass.async_add_executor_job(
                os.path.exists, real_store.path
            )

            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
            await hass.async_block_till_done()
            assert not await hass.async_add_executor_job(
                os.path.exists, real_store.path
            )
            await hass.async_stop()

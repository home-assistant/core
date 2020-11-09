"""Test the Profiler config flow."""
import os

from homeassistant import setup
from homeassistant.components.profiler import (
    CONF_SECONDS,
    SERVICE_MEMORY,
    SERVICE_START,
)
from homeassistant.components.profiler.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_basic_usage(hass, tmpdir):
    """Test we can setup and the service is registered."""
    test_dir = tmpdir.mkdir("profiles")

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_START)

    last_filename = None

    def _mock_path(filename):
        nonlocal last_filename
        last_filename = f"{test_dir}/{filename}"
        return last_filename

    with patch("homeassistant.components.profiler.cProfile.Profile"), patch.object(
        hass.config, "path", _mock_path
    ):
        await hass.services.async_call(DOMAIN, SERVICE_START, {CONF_SECONDS: 0.000001})
        await hass.async_block_till_done()

    assert os.path.exists(last_filename)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_memory_usage(hass, tmpdir):
    """Test we can setup and the service is registered."""
    test_dir = tmpdir.mkdir("profiles")

    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_MEMORY)

    last_filename = None

    def _mock_path(filename):
        nonlocal last_filename
        last_filename = f"{test_dir}/{filename}"
        return last_filename

    with patch("homeassistant.components.profiler.hpy") as mock_hpy, patch.object(
        hass.config, "path", _mock_path
    ):
        await hass.services.async_call(DOMAIN, SERVICE_MEMORY, {CONF_SECONDS: 0.000001})
        await hass.async_block_till_done()

        mock_hpy.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

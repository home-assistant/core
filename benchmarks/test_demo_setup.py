"""CodSpeed benchmark for booting Home Assistant with the demo integration.

The micro benchmarks next to this file isolate single hot paths. This one looks
at the whole picture instead: start an instance, set up ``demo`` (which pulls in
most entity platforms and leaves around 120 entities), and shut it down again.
It is mainly here for the memory instrument, so a change that makes setting up
integrations and entities noticeably more hungry shows up on a pull request.

Run locally with: ``pytest benchmarks --codspeed``.
"""

import asyncio
from unittest.mock import patch

from pytest_codspeed import BenchmarkFixture

from homeassistant.setup import async_setup_component
from tests.common import async_test_home_assistant, mock_storage


async def _async_boot_demo() -> int:
    """Start a fresh instance, set up demo and stop it again."""
    async with async_test_home_assistant() as hass:
        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "demo", {"demo": {}})
        await hass.async_block_till_done()

        entity_count = len(hass.states.async_all())
        await hass.async_stop()

    return entity_count


def test_demo_setup(benchmark: BenchmarkFixture) -> None:
    """Boot a fresh instance with the demo integration.

    Every call builds its own instance on its own loop. CodSpeed calls the
    benchmark once to warm up before measuring, so reusing a single instance
    would leave the measured call with nothing left to set up. It also keeps
    imports out of the measurement: those happen during the warm-up call.

    Storage is mocked so nothing lands on disk, and the legacy device tracker
    is kept from writing its ``known_devices.yaml``.
    """
    with (
        mock_storage(),
        patch("homeassistant.components.device_tracker.legacy.update_config"),
    ):
        entity_count = benchmark(lambda: asyncio.run(_async_boot_demo()))

    assert entity_count > 100

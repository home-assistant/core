"""CodSpeed benchmark for starting Home Assistant.

The micro benchmarks next to this file isolate single hot paths. This one looks
at the whole picture instead: a real ``bootstrap.async_setup_hass`` run against
a config directory with nothing but the default integrations, which boots
around 110 of them while reading and writing real ``.storage`` files. It is
mainly here for the memory instrument, so a change that makes startup
noticeably more hungry shows up on a pull request.

Run locally with: ``pytest benchmarks --codspeed``.
"""

import asyncio
from collections.abc import Generator
from pathlib import Path
import socket
from unittest.mock import patch

import pytest
from pytest_codspeed import BenchmarkFixture

from homeassistant import block_async_io, bootstrap, runner


def _free_port() -> int:
    """Return a TCP port on the loopback interface that is free right now."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]

    return port


async def _async_start_and_stop(config_dir: Path) -> None:
    """Start Home Assistant from ``config_dir``, then stop it again."""
    hass = await bootstrap.async_setup_hass(
        runner.RuntimeConfig(config_dir=str(config_dir), skip_pip=True)
    )
    assert hass is not None
    assert not hass.config.recovery_mode

    await hass.async_start()
    await hass.async_block_till_done()
    await hass.async_stop()


@pytest.fixture(scope="module")
def config_dir(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path]:
    """Return a config directory that has already been booted once.

    The priming boot writes ``.storage``, so every measured boot is a restart
    of an existing installation, which is what users do far more often than a
    fresh install.

    Blocking call detection and logging are set up once per process, and
    bootstrap refuses to do either twice. Blocking call detection is enabled
    for real here, so its wrappers stay active during the measured boots, just
    like in production. Logging setup is skipped altogether, which leaves
    pytest in charge of the log output.
    """
    config_dir = tmp_path_factory.mktemp("startup")
    (config_dir / "configuration.yaml").write_text(
        f"http:\n  server_host: 127.0.0.1\n  server_port: {_free_port()}\n"
    )

    # Importing unittest makes block_async_io think it runs in tests, which
    # skips part of the wrappers. Enable all of them, like production does.
    with patch.object(block_async_io, "_IN_TESTS", False):
        block_async_io.enable()

    with (
        patch("homeassistant.bootstrap.block_async_io.enable"),
        patch("homeassistant.bootstrap.async_enable_logging"),
    ):
        asyncio.run(_async_start_and_stop(config_dir))
        yield config_dir

    # Undo the wrappers again, or they fire on pytest's own teardown. Same as
    # the disable_block_async_io fixture of the test suite.
    calls = block_async_io._BLOCKED_CALLS.calls  # noqa: SLF001
    for blocking_call in calls:
        setattr(
            blocking_call.object, blocking_call.function, blocking_call.original_func
        )
    calls.clear()


def test_startup(benchmark: BenchmarkFixture, config_dir: Path) -> None:
    """Restart Home Assistant with its default integrations.

    Every call builds its own instance on its own loop. Imports happen during
    the priming boot, so they stay out of the measurement.
    """
    benchmark(lambda: asyncio.run(_async_start_and_stop(config_dir)))

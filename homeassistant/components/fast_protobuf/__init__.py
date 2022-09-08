"""The fast_protobuf integration."""
from __future__ import annotations

import asyncio
import contextlib
import glob
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import google.protobuf
from google.protobuf.internal import api_implementation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, callback

PROTOBUF_VERSION = google.protobuf.__version__
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fast protobuf from a config entry."""

    if api_implementation.Type() == "cpp":
        _LOGGER.info(
            "Already using %s C++ implementation of protobuf, enjoy :)",
            PROTOBUF_VERSION,
        )
        return True

    _LOGGER.warning(
        "Building protobuf %s cpp version in the background, this will be cpu intensive",
        PROTOBUF_VERSION,
    )

    @callback
    def _async_build_wheel(event: Event) -> None:
        # Create an untracked task to build the wheel in the background
        # so we don't block shutdown if its not done by the time we exit
        # since they can just try again next time.
        config_dir = hass.config.config_dir
        future = hass.loop.run_in_executor(
            None, build_wheel, config_dir, PROTOBUF_VERSION
        )
        asyncio.ensure_future(future)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_build_wheel)
    )

    return True


def build_wheel(target_dir: str, version: str) -> str:
    """Build a wheel for the current platform."""
    python_bin = sys.executable
    cpu_count = os.cpu_count() or 4
    _LOGGER.info("Building protobuf wheel for %s", version)
    target_dir = os.path.abspath(target_dir)
    with tempfile.TemporaryDirectory(
        dir=os.path.expanduser("~")  # /tmp may be non-executable
    ) as tmp_dist_dir:
        with contextlib.suppress(subprocess.CalledProcessError):
            run_command(
                "apk add "
                "autoconf automake libtool m4 gcc musl-dev "
                "openssl-dev libffi-dev zlib-dev jpeg-dev g++ make"
            )
        run_command(
            f"git clone --depth 1 --branch v{version}"
            f" https://github.com/protocolbuffers/protobuf {tmp_dist_dir}/protobuf"
        )
        run_command(f"cd {tmp_dist_dir}/protobuf && /bin/sh ./autogen.sh")
        run_command(
            f'cd {tmp_dist_dir}/protobuf && /bin/sh ./configure "CFLAGS=-fPIC" "CXXFLAGS=-fPIC"'
        )
        run_command(f"cd {tmp_dist_dir}/protobuf && make -j{cpu_count}")
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            f"MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../src/.libs "
            f"{python_bin} setup.py build --cpp_implementation --compile_static_extension"
        )
        run_command(
            f"cd {tmp_dist_dir}/protobuf/python && "
            f"MAKEFLAGS=-j{cpu_count} LD_LIBRARY_PATH=../src/.libs "
            f"{python_bin} setup.py bdist_wheel --cpp_implementation --compile_static_extension"
        )
        wheel_file = glob.glob(f"{tmp_dist_dir}/protobuf/python/dist/*.whl")[0]
        _LOGGER.info("Built wheel %s", wheel_file)
        result_basename = os.path.basename(wheel_file)
        result_path = os.path.join(target_dir, result_basename)
        shutil.copy(wheel_file, result_path)
        _LOGGER.info("Moved into file: %s", result_path)
    _LOGGER.info("Finished building wheel: %s", result_path)
    run_command(
        f"{python_bin} -m pip install --upgrade --no-deps "
        f"--force-reinstall protobuf {result_path}"
    )
    _LOGGER.warning("Restart Home Assistant to use the new wheel")
    return result_path


def run_command(
    cmd: str, env: dict[str, str] | None = None, timeout: int | None = None
) -> None:
    """Implement subprocess.run but handle timeout different."""
    subprocess.run(
        cmd,
        shell=True,  # nosec
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env,
        timeout=timeout,
    )

"""Test the Home Assistant package init."""

import subprocess
import sys

IMPORT_TIMEOUT = 60


def test_codec_reexports_resolve_before_the_event_loop() -> None:
    """Importing Home Assistant must leave no lazy codec import for the loop.

    Probatio resolves to_field_list through a lazy import on first attribute
    access, and config flow forms render with it from inside the event loop,
    where that import is a blocking call. A clean interpreter is the only way to
    see this: anything the test suite imported first would hide it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import homeassistant, probatio; print('to_field_list' in vars(probatio))",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=IMPORT_TIMEOUT,
    )

    assert result.stdout.strip() == "True"

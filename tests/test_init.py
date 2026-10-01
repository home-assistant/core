"""Test the Home Assistant package init."""

import subprocess
import sys

IMPORT_TIMEOUT = 60


def test_probatio_codecs_is_imported_before_the_event_loop() -> None:
    """Starting up must leave no lazy codec import for the loop to do.

    Probatio resolves to_field_list and to_openapi through a lazy import of
    probatio.codecs on first attribute access, and both are reached from the
    event loop: the first renders every config flow form, the second builds the
    tool schemas for a conversation turn. Importing a name binds it while the
    module itself is imported, which happens off the loop, and that puts
    probatio.codecs in sys.modules for every other lazy name too.

    A clean interpreter is the only way to see this: anything the test suite
    imported first would hide it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, homeassistant.bootstrap;"
            " print('probatio.codecs' in sys.modules)",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=IMPORT_TIMEOUT,
    )

    assert result.stdout.strip() == "True"

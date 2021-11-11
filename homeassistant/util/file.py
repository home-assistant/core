"""File utility functions."""
from __future__ import annotations

import logging
import os
import tempfile

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class WriteError(HomeAssistantError):
    """Error writing the data."""


def write_utf8_file(
    filename: str,
    utf8_data: str,
    private: bool = False,
) -> None:
    """Write a file and rename it into place.

    Writes all or nothing.
    """

    tmp_filename = ""
    tmp_path = os.path.split(filename)[0]
    try:
        # Modern versions of Python tempfile create this file with mode 0o600
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=tmp_path, delete=False
        ) as fdesc:
            fdesc.write(utf8_data)
            tmp_filename = fdesc.name
        if not private:
            os.chmod(tmp_filename, 0o644)
        os.replace(tmp_filename, filename)
    except OSError as error:
        _LOGGER.exception("Saving file failed: %s", filename)
        raise WriteError(error) from error
    finally:
        if os.path.exists(tmp_filename):
            try:
                os.remove(tmp_filename)
            except OSError as err:
                # If we are cleaning up then something else went wrong, so
                # we should suppress likely follow-on errors in the cleanup
                _LOGGER.error(
                    "File replacement cleanup failed for %s while saving %s: %s",
                    tmp_filename,
                    filename,
                    err,
                )

"""File utility functions."""
from __future__ import annotations

import logging
import os
import tempfile

from atomicwrites import AtomicWriter

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class WriteError(HomeAssistantError):
    """Error writing the data."""


def write_utf8_file_atomic(
    filename: str, utf8_data: bytes | str, private: bool = False, mode: str = "w"
) -> None:
    """Write a file and rename it into place using atomicwrites.

    Writes all or nothing.

    This function uses fsync under the hood. It should
    only be used to write mission critical files as
    fsync can block for a few seconds or longer is the
    disk is busy.

    Using this function frequently will significantly
    negatively impact performance.
    """
    try:
        with AtomicWriter(filename, mode=mode, overwrite=True).open() as fdesc:
            if not private:
                os.fchmod(fdesc.fileno(), 0o644)
            fdesc.write(utf8_data)
    except OSError as error:
        _LOGGER.exception("Saving file failed: %s", filename)
        raise WriteError(error) from error


def write_utf8_file(
    filename: str, utf8_data: bytes | str, private: bool = False, mode: str = "w"
) -> None:
    """Write a file and rename it into place.

    Writes all or nothing.
    """
    tmp_filename = ""
    encoding = "utf-8" if "b" not in mode else None
    try:
        # Modern versions of Python tempfile create this file with mode 0o600
        with tempfile.NamedTemporaryFile(
            mode=mode, encoding=encoding, dir=os.path.dirname(filename), delete=False
        ) as fdesc:
            fdesc.write(utf8_data)
            tmp_filename = fdesc.name
            if not private:
                os.fchmod(fdesc.fileno(), 0o644)
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

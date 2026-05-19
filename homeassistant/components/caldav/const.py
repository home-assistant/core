"""Constants for CalDAV."""

from typing import Final

try:
    from niquests.exceptions import ConnectionError as NiquestsConnectionError
except ImportError:

    class NiquestsConnectionError(Exception):  # type: ignore[no-redef]
        """Placeholder — never raised when niquests is absent."""


DOMAIN: Final = "caldav"
TIMEOUT: Final = 30

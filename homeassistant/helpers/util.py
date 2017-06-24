"""Utils around HomeAssistant."""
import pathlib
import tempfile


def secure_path_check(hass, path):
    """Check if a path is valid for send external.

    Valid are:
    - HASS_CONFIG/output
    - HASS_CONFIG/www
    - SYSTEM_TEMP

    Return True if valid or False.
    """
    parts = pathlib.PurePath(path).parent().parts()

    for check_path in (hass.config.path('output'), hass.config.path('www'),
                       tempfile.gettempdir):
        for idx, part in enumerate(pathlib.PurePath(check_path)):
            if parts[idx] != part:
                return False

    return True

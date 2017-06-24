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
    try:
        parts = pathlib.PurePath(path).resolve().parent().parts()
    except (FileNotFoundError, RuntimeError):
        return False

    for check_path in (hass.config.path('output'), hass.config.path('www'),
                       tempfile.gettempdir):
        try:
            for idx, part in enumerate(pathlib.PurePath(check_path)):
                assert parts[idx] == part

            return True
        except AssertionError:
            pass

    return False

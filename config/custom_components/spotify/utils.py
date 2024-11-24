# noqa: ignore=all

from copy import deepcopy

# # get smartinspect logger reference; create a new session for this module name.
# from smartinspectpython.siauto import SIAuto, SILevel, SISession, SIColors
# import logging
# _logsi:SISession = SIAuto.Si.GetSession(__name__)
# if (_logsi == None):
#     _logsi = SIAuto.Si.AddSession(__name__, True)
# _logsi.SystemLogger = logging.getLogger(__name__)


def passwordMaskDictionary(inputObj: dict) -> dict:
    """
    Checks keys in a dictionary any keys that contain `password` and masks the
    value so that the password is not displayed in a trace file.

    Args:
        inputObj (dict):
            Dictionary object to check.

    Returns:
        A copy of the `inputObj` source dictionary with passwor(s) masked.

    Note that this method performs a simple copy of the dictionary.
    """
    # if input is null then don't bother.
    if inputObj is None:
        return inputObj

    # create a new dictionary.
    result: dict = {}

    # process keys in the dictionary.
    key: str
    for key in inputObj.keys():
        keyLower: str = key.lower()
        if keyLower.find("password") == -1:
            result[key] = inputObj[key]
        else:
            value: str = inputObj[key]
            if (value is not None) and (isinstance(value, str)):
                result[key] = "".ljust(len(value), "*")

    return result


def passwordMaskString(inputObj: str) -> str:
    """
    Checks a string for a password value and masks the value so that the password is not displayed
    in a trace file.

    Args:
        inputObj (str):
            String object to check.

    Returns:
        A copy of the `inputObj` value with password masked.
    """
    # if input is null then don't bother.
    if inputObj is None:
        return inputObj

    # create a new value.
    result: str = "".ljust(len(inputObj), "*")

    return result


def validateDelay(delay: float, default: float = 0.5, maxDelay: float = 10) -> float:
    """
    Validates a delay value.

    Args:
        delay (int):
            The delay value to validate.
        default (int):
            The default delay value to set if the user-input delay is not valid.
        maxDelay (int):
            The maximum delay value allowed.
            Default is 10.
    """
    if isinstance(delay, int):
        delay = float(delay)

    if (not isinstance(delay, float)) or (delay < 0):
        result = default
    elif delay > maxDelay:
        result = maxDelay
    else:
        result = delay

    return result


def positionHMS_fromMilliSeconds(
    position: int,
) -> float:
    """
    Converts an integer position value from milliseconds to a string value in H:MM:SS format.

    Args:
        position (int):
            The position value (as specified in milliseconds) to convert.
    """
    result: str = "0:00:00"

    # validations.
    if isinstance(position, float):
        position = int(position)
    if (position is None) or (not isinstance(position, int)) or (position < 1):
        return result

    # convert milliseconds to H:MM:SS string format.
    nSeconds = position / 1000
    mm, ss = divmod(nSeconds, 60)  # get minutes and seconds first
    hh, mm = divmod(mm, 60)  # get hours next
    result = "%d:%02d:%02d" % (hh, mm, ss)  # format to hh:mm:ss

    # return result to caller.
    return result


def positionHMS_fromSeconds(
    position: int,
) -> float:
    """
    Converts an integer position value from seconds to a string value in H:MM:SS format.

    Args:
        position (int):
            The position value (as specified in seconds) to convert.
    """
    result: str = "0:00:00"

    # validations.
    if isinstance(position, float):
        position = int(position)
    if (position is None) or (position < 1):
        return result

    # convert seconds to H:MM:SS string format.
    nSeconds = int(position)
    mm, ss = divmod(nSeconds, 60)  # get minutes and seconds first
    hh, mm = divmod(mm, 60)  # get hours next
    result = "%d:%02d:%02d" % (hh, mm, ss)  # format to hh:mm:ss

    # return result to caller.
    return result

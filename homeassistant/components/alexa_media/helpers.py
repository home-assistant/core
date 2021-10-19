"""
Helper functions for Alexa Media Player.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
import hashlib
import logging
from typing import Any, Callable, Dict, List, Optional, Text

from alexapy import AlexapyLoginCloseRequested, AlexapyLoginError, hide_email
from alexapy.alexalogin import AlexaLogin
from homeassistant.const import CONF_EMAIL, CONF_URL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent
import wrapt

from .const import DATA_ALEXAMEDIA, EXCEPTION_TEMPLATE

_LOGGER = logging.getLogger(__name__)


async def add_devices(
    account: Text,
    devices: List[EntityComponent],
    add_devices_callback: Callable,
    include_filter: Optional[List[Text]] = None,
    exclude_filter: Optional[List[Text]] = None,
) -> bool:
    """Add devices using add_devices_callback."""
    include_filter = [] or include_filter
    exclude_filter = [] or exclude_filter
    new_devices = []
    for device in devices:
        if (
            include_filter
            and device.name not in include_filter
            or exclude_filter
            and device.name in exclude_filter
        ):
            _LOGGER.debug("%s: Excluding device: %s", account, device)
            continue
        new_devices.append(device)
    devices = new_devices
    if devices:
        _LOGGER.debug("%s: Adding %s", account, devices)
        try:
            add_devices_callback(devices, False)
            return True
        except HomeAssistantError as exception_:
            message = exception_.message  # type: str
            if message.startswith("Entity id already exists"):
                _LOGGER.debug("%s: Device already added: %s", account, message)
            else:
                _LOGGER.debug(
                    "%s: Unable to add devices: %s : %s", account, devices, message
                )
        except BaseException as ex:  # pylint: disable=broad-except
            _LOGGER.debug(
                "%s: Unable to add devices: %s",
                account,
                EXCEPTION_TEMPLATE.format(type(ex).__name__, ex.args),
            )
    else:
        return True
    return False


def retry_async(
    limit: int = 5, delay: float = 1, catch_exceptions: bool = True
) -> Callable:
    """Wrap function with retry logic.

    The function will retry until true or the limit is reached. It will delay
    for the period of time specified exponentially increasing the delay.

    Parameters
    ----------
    limit : int
        The max number of retries.
    delay : float
        The delay in seconds between retries.
    catch_exceptions : bool
        Whether exceptions should be caught and treated as failures or thrown.
    Returns
    -------
    def
        Wrapped function.

    """

    def wrap(func) -> Callable:
        import asyncio
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            _LOGGER.debug(
                "%s.%s: Trying with limit %s delay %s catch_exceptions %s",
                func.__module__[func.__module__.find(".") + 1 :],
                func.__name__,
                limit,
                delay,
                catch_exceptions,
            )
            retries: int = 0
            result: bool = False
            next_try: int = 0
            while not result and retries < limit:
                if retries != 0:
                    next_try = delay * 2 ** retries
                    await asyncio.sleep(next_try)
                retries += 1
                try:
                    result = await func(*args, **kwargs)
                except Exception as ex:  # pylint: disable=broad-except
                    if not catch_exceptions:
                        raise
                    _LOGGER.debug(
                        "%s.%s: failure caught due to exception: %s",
                        func.__module__[func.__module__.find(".") + 1 :],
                        func.__name__,
                        EXCEPTION_TEMPLATE.format(type(ex).__name__, ex.args),
                    )
                _LOGGER.debug(
                    "%s.%s: Try: %s/%s after waiting %s seconds result: %s",
                    func.__module__[func.__module__.find(".") + 1 :],
                    func.__name__,
                    retries,
                    limit,
                    next_try,
                    result,
                )
            return result

        return wrapper

    return wrap


@wrapt.decorator
async def _catch_login_errors(func, instance, args, kwargs) -> Any:
    """Detect AlexapyLoginError and attempt relogin."""

    result = None
    if instance is None and args:
        instance = args[0]
    if hasattr(instance, "check_login_changes"):
        # _LOGGER.debug(
        #     "%s checking for login changes", instance,
        # )
        instance.check_login_changes()
    try:
        result = await func(*args, **kwargs)
    except AlexapyLoginCloseRequested:
        _LOGGER.debug(
            "%s.%s: Ignoring attempt to access Alexa after HA shutdown",
            func.__module__[func.__module__.find(".") + 1 :],
            func.__name__,
        )
        return None
    except AlexapyLoginError as ex:
        login = None
        email = None
        all_args = list(args) + list(kwargs.values())
        # _LOGGER.debug("Func %s instance %s %s %s", func, instance, args, kwargs)
        if instance:
            if hasattr(instance, "_login"):
                login = instance._login
                hass = instance.hass
        else:
            for arg in all_args:
                _LOGGER.debug("Checking %s", arg)

                if isinstance(arg, AlexaLogin):
                    login = arg
                    break
                if hasattr(arg, "_login"):
                    login = instance._login
                    hass = instance.hass
                    break

        if login:
            email = login.email
            _LOGGER.debug(
                "%s.%s: detected bad login for %s: %s",
                func.__module__[func.__module__.find(".") + 1 :],
                func.__name__,
                hide_email(email),
                EXCEPTION_TEMPLATE.format(type(ex).__name__, ex.args),
            )
        try:
            hass
        except NameError:
            hass = None
        report_relogin_required(hass, login, email)
        return None
    return result


def report_relogin_required(hass, login, email) -> bool:
    """Send message for relogin required."""
    if hass and login and email:
        if login.status:
            _LOGGER.debug(
                "Reporting need to relogin to %s with %s stats: %s",
                login.url,
                hide_email(email),
                login.stats,
            )
            hass.bus.async_fire(
                "alexa_media_relogin_required",
                event_data={
                    "email": hide_email(email),
                    "url": login.url,
                    "stats": login.stats,
                },
            )
            return True
    return False


def _existing_serials(hass, login_obj) -> List:
    email: Text = login_obj.email
    existing_serials = (
        list(
            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
                "media_player"
            ].keys()
        )
        if "entities" in (hass.data[DATA_ALEXAMEDIA]["accounts"][email])
        else []
    )
    for serial in existing_serials:
        device = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"][
            "media_player"
        ][serial]
        if "appDeviceList" in device and device["appDeviceList"]:
            apps = list(
                map(
                    lambda x: x["serialNumber"] if "serialNumber" in x else None,
                    device["appDeviceList"],
                )
            )
            # _LOGGER.debug("Combining %s with %s",
            #               existing_serials, apps)
            existing_serials = existing_serials + apps
    return existing_serials


async def calculate_uuid(hass, email: Text, url: Text) -> dict:
    """Return uuid and index of email/url.

    Args
        hass (bool): Hass entity
        url (Text): url for account
        email (Text): email for account

    Returns
        dict: dictionary with uuid and index

    """
    result = {}
    return_index = 0
    if hass.config_entries.async_entries(DATA_ALEXAMEDIA):
        for index, entry in enumerate(
            hass.config_entries.async_entries(DATA_ALEXAMEDIA)
        ):
            if entry.data.get(CONF_EMAIL) == email and entry.data.get(CONF_URL) == url:
                return_index = index
                break
    uuid = await hass.helpers.instance_id.async_get()
    result["uuid"] = hex(
        int(uuid, 16)
        # increment uuid for second accounts
        + return_index
        # hash email/url in case HA uuid duplicated
        + int(hashlib.md5((email.lower() + url.lower()).encode()).hexdigest(), 16)
    )[-32:]
    result["index"] = return_index
    _LOGGER.debug("%s: Returning uuid %s", hide_email(email), result)
    return result


def alarm_just_dismissed(
    alarm: Dict[Text, Any],
    previous_status: Optional[Text],
    previous_version: Optional[Text],
) -> bool:
    """Given the previous state of an alarm, determine if it has just been dismissed."""

    if previous_status not in ("SNOOZED", "ON"):
        # The alarm had to be in a status that supported being dismissed
        return False

    if previous_version is None:
        # The alarm was probably just created
        return False

    if not alarm:
        # The alarm that was probably just deleted.
        return False

    if alarm.get("status") not in ("OFF", "ON"):
        # A dismissed alarm is guaranteed to be turned off(one-off alarm) or left on(recurring alarm)
        return False

    if previous_version == alarm.get("version"):
        # A dismissal always has a changed version.
        return False

    if int(alarm.get("version", "0")) > 1 + int(previous_version):
        # This is an absurd thing to check, but it solves many, many edge cases.
        # Experimentally, when an alarm is dismissed, the version always increases by 1
        # When an alarm is edited either via app or voice, its version always increases by 2+
        return False

    # It seems obvious that a check involving time should be necessary. It is not.
    # We know there was a change and that it wasn't an edit.
    # We also know the alarm's status rules out a snooze.
    # The only remaining possibility is that this alarm was just dismissed.
    return True

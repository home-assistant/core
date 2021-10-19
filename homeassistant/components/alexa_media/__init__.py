"""
Support to interface with Alexa Devices.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
import asyncio
from datetime import datetime, timedelta
from json import JSONDecodeError
import logging
import time
from typing import Optional, Text

from alexapy import (
    AlexaAPI,
    AlexaLogin,
    AlexapyConnectionError,
    AlexapyLoginError,
    WebsocketEchoClient,
    __version__ as alexapy_version,
    hide_email,
    hide_serial,
    obfuscate,
)
import async_timeout
from homeassistant import util
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_EMAIL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt, slugify
import voluptuous as vol

from .alexa_entity import AlexaEntityData, get_entity_data, parse_alexa_entities
from .config_flow import in_progess_instances
from .const import (
    ALEXA_COMPONENTS,
    CONF_ACCOUNTS,
    CONF_COOKIES_TXT,
    CONF_DEBUG,
    CONF_EXCLUDE_DEVICES,
    CONF_EXTENDED_ENTITY_DISCOVERY,
    CONF_INCLUDE_DEVICES,
    CONF_OAUTH,
    CONF_OAUTH_LOGIN,
    CONF_OTPSECRET,
    CONF_QUEUE_DELAY,
    DATA_ALEXAMEDIA,
    DATA_LISTENER,
    DEFAULT_EXTENDED_ENTITY_DISCOVERY,
    DEFAULT_QUEUE_DELAY,
    DEPENDENT_ALEXA_COMPONENTS,
    DOMAIN,
    ISSUE_URL,
    MIN_TIME_BETWEEN_FORCED_SCANS,
    MIN_TIME_BETWEEN_SCANS,
    SCAN_INTERVAL,
    STARTUP,
)
from .helpers import (
    _catch_login_errors,
    _existing_serials,
    alarm_just_dismissed,
    calculate_uuid,
)
from .notify import async_unload_entry as notify_async_unload_entry
from .services import AlexaMediaServices

_LOGGER = logging.getLogger(__name__)


ACCOUNT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_INCLUDE_DEVICES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_DEVICES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ACCOUNTS): vol.All(
                    cv.ensure_list, [ACCOUNT_CONFIG_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config, discovery_info=None):
    # pylint: disable=unused-argument
    """Set up the Alexa domain."""
    if DOMAIN not in config:
        _LOGGER.debug(
            "Nothing to import from configuration.yaml, loading from Integrations",
        )
        return True

    domainconfig = config.get(DOMAIN)
    for account in domainconfig[CONF_ACCOUNTS]:
        entry_found = False
        _LOGGER.debug(
            "Importing config information for %s - %s from configuration.yaml",
            hide_email(account[CONF_EMAIL]),
            account[CONF_URL],
        )
        if hass.config_entries.async_entries(DOMAIN):
            _LOGGER.debug("Found existing config entries")
            for entry in hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.data.get(CONF_EMAIL) == account[CONF_EMAIL]
                    and entry.data.get(CONF_URL) == account[CONF_URL]
                ):
                    _LOGGER.debug("Updating existing entry")
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_EMAIL: account[CONF_EMAIL],
                            CONF_PASSWORD: account[CONF_PASSWORD],
                            CONF_URL: account[CONF_URL],
                            CONF_DEBUG: account[CONF_DEBUG],
                            CONF_INCLUDE_DEVICES: account[CONF_INCLUDE_DEVICES],
                            CONF_EXCLUDE_DEVICES: account[CONF_EXCLUDE_DEVICES],
                            CONF_SCAN_INTERVAL: account[
                                CONF_SCAN_INTERVAL
                            ].total_seconds(),
                            CONF_OAUTH: account.get(CONF_OAUTH, {}),
                            CONF_OTPSECRET: account.get(CONF_OTPSECRET, ""),
                            CONF_OAUTH_LOGIN: account.get(CONF_OAUTH_LOGIN, True),
                        },
                    )
                    entry_found = True
                    break
        if not entry_found:
            _LOGGER.debug("Creating new config entry")
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_EMAIL: account[CONF_EMAIL],
                        CONF_PASSWORD: account[CONF_PASSWORD],
                        CONF_URL: account[CONF_URL],
                        CONF_DEBUG: account[CONF_DEBUG],
                        CONF_INCLUDE_DEVICES: account[CONF_INCLUDE_DEVICES],
                        CONF_EXCLUDE_DEVICES: account[CONF_EXCLUDE_DEVICES],
                        CONF_SCAN_INTERVAL: account[CONF_SCAN_INTERVAL].total_seconds(),
                        CONF_OAUTH: account.get(CONF_OAUTH, {}),
                        CONF_OTPSECRET: account.get(CONF_OTPSECRET, ""),
                        CONF_OAUTH_LOGIN: account.get(CONF_OAUTH_LOGIN, True),
                    },
                )
            )
    return True


# @retry_async(limit=5, delay=5, catch_exceptions=True)
async def async_setup_entry(hass, config_entry):
    """Set up Alexa Media Player as config entry."""

    async def close_alexa_media(event=None) -> None:
        """Clean up Alexa connections."""
        _LOGGER.debug("Received shutdown request: %s", event)
        if hass.data.get(DATA_ALEXAMEDIA, {}).get("accounts"):
            for email, _ in hass.data[DATA_ALEXAMEDIA]["accounts"].items():
                await close_connections(hass, email)

    async def complete_startup(event=None) -> None:
        """Run final tasks after startup."""
        _LOGGER.debug("Completing remaining startup tasks.")
        await asyncio.sleep(10)
        if hass.data[DATA_ALEXAMEDIA].get("notify_service"):
            notify = hass.data[DATA_ALEXAMEDIA].get("notify_service")
            _LOGGER.debug("Refreshing notify targets")
            await notify.async_register_services()

    async def relogin(event=None) -> None:
        """Relogin to Alexa."""
        if hide_email(email) == event.data.get("email"):
            _LOGGER.debug("%s: Received relogin request: %s", hide_email(email), event)
            login_obj: AlexaLogin = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get(
                "login_obj"
            )
            uuid = (await calculate_uuid(hass, email, url))["uuid"]
            if login_obj is None:
                login_obj = AlexaLogin(
                    url=url,
                    email=email,
                    password=password,
                    outputpath=hass.config.path,
                    debug=account.get(CONF_DEBUG),
                    otp_secret=account.get(CONF_OTPSECRET, ""),
                    oauth=account.get(CONF_OAUTH, {}),
                    uuid=uuid,
                    oauth_login=bool(
                        account.get(CONF_OAUTH, {}).get("access_token")
                        or account.get(CONF_OAUTH_LOGIN)
                    ),
                )
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["login_obj"] = login_obj
            await login_obj.reset()
            # await login_obj.login()
            if await test_login_status(hass, config_entry, login_obj):
                await setup_alexa(hass, config_entry, login_obj)

    async def login_success(event=None) -> None:
        """Relogin to Alexa."""
        if hide_email(email) == event.data.get("email"):
            _LOGGER.debug("Received Login success: %s", event)
            login_obj: AlexaLogin = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get(
                "login_obj"
            )
            await setup_alexa(hass, config_entry, login_obj)

    if not hass.data.get(DATA_ALEXAMEDIA):
        _LOGGER.info(STARTUP)
        _LOGGER.info("Loaded alexapy==%s", alexapy_version)
    hass.data.setdefault(
        DATA_ALEXAMEDIA, {"accounts": {}, "config_flows": {}, "notify_service": None}
    )
    if not hass.data[DATA_ALEXAMEDIA].get("accounts"):
        hass.data[DATA_ALEXAMEDIA] = {
            "accounts": {},
            "config_flows": {},
        }
    account = config_entry.data
    email = account.get(CONF_EMAIL)
    password = account.get(CONF_PASSWORD)
    url = account.get(CONF_URL)
    hass.data[DATA_ALEXAMEDIA]["accounts"].setdefault(
        email,
        {
            "coordinator": None,
            "config_entry": config_entry,
            "setup_alexa": setup_alexa,
            "devices": {
                "media_player": {},
                "switch": {},
                "guard": [],
                "light": [],
                "temperature": [],
            },
            "entities": {
                "media_player": {},
                "switch": {},
                "sensor": {},
                "light": [],
                "alarm_control_panel": {},
            },
            "excluded": {},
            "new_devices": True,
            "websocket_lastattempt": 0,
            "websocketerror": 0,
            "websocket_commands": {},
            "websocket_activity": {"serials": {}, "refreshed": {}},
            "websocket": None,
            "auth_info": None,
            "second_account_index": 0,
            "should_get_network": True,
            "options": {
                CONF_QUEUE_DELAY: config_entry.options.get(
                    CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY
                ),
                CONF_EXTENDED_ENTITY_DISCOVERY: config_entry.options.get(
                    CONF_EXTENDED_ENTITY_DISCOVERY, DEFAULT_EXTENDED_ENTITY_DISCOVERY
                ),
            },
            DATA_LISTENER: [config_entry.add_update_listener(update_listener)],
        },
    )
    uuid_dict = await calculate_uuid(hass, email, url)
    uuid = uuid_dict["uuid"]
    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["second_account_index"] = uuid_dict[
        "index"
    ]
    login: AlexaLogin = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get(
        "login_obj",
        AlexaLogin(
            url=url,
            email=email,
            password=password,
            outputpath=hass.config.path,
            debug=account.get(CONF_DEBUG),
            otp_secret=account.get(CONF_OTPSECRET, ""),
            oauth=account.get(CONF_OAUTH, {}),
            uuid=uuid,
            oauth_login=bool(
                account.get(CONF_OAUTH, {}).get("access_token")
                or account.get(CONF_OAUTH_LOGIN)
            ),
        ),
    )
    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["login_obj"] = login
    if not hass.data[DATA_ALEXAMEDIA]["accounts"][email]["second_account_index"]:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_alexa_media)
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, complete_startup)
    hass.bus.async_listen("alexa_media_relogin_required", relogin)
    hass.bus.async_listen("alexa_media_relogin_success", login_success)
    await login.login(cookies=await login.load_cookie())
    if await test_login_status(hass, config_entry, login):
        await setup_alexa(hass, config_entry, login)
        return True
    return False


async def setup_alexa(hass, config_entry, login_obj: AlexaLogin):
    """Set up a alexa api based on host parameter."""

    async def async_update_data() -> Optional[AlexaEntityData]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.

        This will ping Alexa API to identify all devices, bluetooth, and the last
        called device.

        If any guards, temperature sensors, or lights are configured, their
        current state will be acquired. This data is returned directly so that it is available on the coordinator.

        This will add new devices and services when discovered. By default this
        runs every SCAN_INTERVAL seconds unless another method calls it. if
        websockets is connected, it will increase the delay 10-fold between updates.
        While throttled at MIN_TIME_BETWEEN_SCANS, care should be taken to
        reduce the number of runs to avoid flooding. Slow changing states
        should be checked here instead of in spawned components like
        media_player since this object is one per account.
        Each AlexaAPI call generally results in two webpage requests.
        """
        email = config.get(CONF_EMAIL)
        login_obj = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["login_obj"]
        if (
            email not in hass.data[DATA_ALEXAMEDIA]["accounts"]
            or not login_obj.status.get("login_successful")
            or login_obj.session.closed
            or login_obj.close_requested
        ):
            return
        existing_serials = _existing_serials(hass, login_obj)
        existing_entities = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
            "media_player"
        ].values()
        auth_info = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get("auth_info")
        new_devices = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["new_devices"]
        should_get_network = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "should_get_network"
        ]
        extended_entity_discovery = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "options"
        ].get(CONF_EXTENDED_ENTITY_DISCOVERY)

        devices = {}
        bluetooth = {}
        preferences = {}
        dnd = {}
        raw_notifications = {}
        entity_state = {}
        tasks = [
            AlexaAPI.get_devices(login_obj),
            AlexaAPI.get_bluetooth(login_obj),
            AlexaAPI.get_device_preferences(login_obj),
            AlexaAPI.get_dnd_state(login_obj),
        ]
        if new_devices:
            tasks.append(AlexaAPI.get_authentication(login_obj))

        entities_to_monitor = set()
        for sensor in hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
            "sensor"
        ].values():
            temp = sensor.get("Temperature")
            if temp and temp.enabled:
                entities_to_monitor.add(temp.alexa_entity_id)

        for light in hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"]["light"]:
            if light.enabled:
                entities_to_monitor.add(light.alexa_entity_id)

        for guard in hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
            "alarm_control_panel"
        ].values():
            if guard.enabled:
                entities_to_monitor.add(guard.unique_id)

        if entities_to_monitor:
            tasks.append(get_entity_data(login_obj, list(entities_to_monitor)))

        if should_get_network:
            tasks.append(AlexaAPI.get_network_details(login_obj))

        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                (
                    devices,
                    bluetooth,
                    preferences,
                    dnd,
                    *optional_task_results,
                ) = await asyncio.gather(*tasks)

                if should_get_network:
                    _LOGGER.debug(
                        "Alexa entities have been loaded. Prepared for discovery."
                    )
                    alexa_entities = parse_alexa_entities(optional_task_results.pop())
                    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"].update(
                        alexa_entities
                    )
                    hass.data[DATA_ALEXAMEDIA]["accounts"][email][
                        "should_get_network"
                    ] = False

                    # First run is a special case. Get the state of all entities(including disabled)
                    # This ensures all entities have state during startup without needing to request coordinator refresh
                    for typeOfEntity, entities in alexa_entities.items():
                        if typeOfEntity == "guard" or extended_entity_discovery:
                            for entity in entities:
                                entities_to_monitor.add(entity.get("id"))
                    entity_state = await get_entity_data(
                        login_obj, list(entities_to_monitor)
                    )
                elif entities_to_monitor:
                    entity_state = optional_task_results.pop()

                if new_devices:
                    auth_info = optional_task_results.pop()
                    _LOGGER.debug(
                        "%s: Found %s devices, %s bluetooth",
                        hide_email(email),
                        len(devices) if devices is not None else "",
                        len(bluetooth.get("bluetoothStates", []))
                        if bluetooth is not None
                        else "",
                    )

            await process_notifications(login_obj, raw_notifications)
            # Process last_called data to fire events
            await update_last_called(login_obj)
        except (AlexapyLoginError, JSONDecodeError):
            _LOGGER.debug(
                "%s: Alexa API disconnected; attempting to relogin : status %s",
                hide_email(email),
                login_obj.status,
            )
            if login_obj.status:
                hass.bus.async_fire(
                    "alexa_media_relogin_required",
                    event_data={"email": hide_email(email), "url": login_obj.url},
                )
            return
        except BaseException as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

        new_alexa_clients = []  # list of newly discovered device names
        exclude_filter = []
        include_filter = []

        for device in devices:
            serial = device["serialNumber"]
            dev_name = device["accountName"]
            if include and dev_name not in include:
                include_filter.append(dev_name)
                if "appDeviceList" in device:
                    for app in device["appDeviceList"]:
                        (
                            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["excluded"][
                                app["serialNumber"]
                            ]
                        ) = device
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["excluded"][
                    serial
                ] = device
                continue
            if exclude and dev_name in exclude:
                exclude_filter.append(dev_name)
                if "appDeviceList" in device:
                    for app in device["appDeviceList"]:
                        (
                            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["excluded"][
                                app["serialNumber"]
                            ]
                        ) = device
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["excluded"][
                    serial
                ] = device
                continue

            if (
                dev_name not in include_filter
                and device.get("capabilities")
                and not any(
                    x in device["capabilities"]
                    for x in ["MUSIC_SKILL", "TIMERS_AND_ALARMS", "REMINDERS"]
                )
            ):
                # skip devices without music or notification skill
                _LOGGER.debug("Excluding %s for lacking capability", dev_name)
                continue

            if "bluetoothStates" in bluetooth:
                for b_state in bluetooth["bluetoothStates"]:
                    if serial == b_state["deviceSerialNumber"]:
                        device["bluetooth_state"] = b_state
                        break

            if "devicePreferences" in preferences:
                for dev in preferences["devicePreferences"]:
                    if dev["deviceSerialNumber"] == serial:
                        device["locale"] = dev["locale"]
                        device["timeZoneId"] = dev["timeZoneId"]
                        _LOGGER.debug(
                            "%s: Locale %s timezone %s",
                            dev_name,
                            device["locale"],
                            device["timeZoneId"],
                        )
                        break

            if "doNotDisturbDeviceStatusList" in dnd:
                for dev in dnd["doNotDisturbDeviceStatusList"]:
                    if dev["deviceSerialNumber"] == serial:
                        device["dnd"] = dev["enabled"]
                        _LOGGER.debug("%s: DND %s", dev_name, device["dnd"])
                        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"][
                            "switch"
                        ].setdefault(serial, {"dnd": True})

                        break
            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["auth_info"] = device[
                "auth_info"
            ] = auth_info
            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"]["media_player"][
                serial
            ] = device

            if serial not in existing_serials:
                new_alexa_clients.append(dev_name)
            elif (
                serial in existing_serials
                and hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
                    "media_player"
                ].get(serial)
                and hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
                    "media_player"
                ]
                .get(serial)
                .enabled
            ):
                await hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][
                    "media_player"
                ].get(serial).refresh(device, skip_api=True)
        _LOGGER.debug(
            "%s: Existing: %s New: %s;"
            " Filtered out by not being in include: %s "
            "or in exclude: %s",
            hide_email(email),
            list(existing_entities),
            new_alexa_clients,
            include_filter,
            exclude_filter,
        )

        if new_alexa_clients:
            cleaned_config = config.copy()
            cleaned_config.pop(CONF_PASSWORD, None)
            # CONF_PASSWORD contains sensitive info which is no longer needed
            for component in ALEXA_COMPONENTS:
                entry_setup = len(
                    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["entities"][component]
                )
                if not entry_setup:
                    _LOGGER.debug("Loading config entry for %s", component)
                    hass.async_add_job(
                        hass.config_entries.async_forward_entry_setup(
                            config_entry, component
                        )
                    )
                else:
                    _LOGGER.debug("Loading %s", component)
                    hass.async_create_task(
                        async_load_platform(
                            hass,
                            component,
                            DOMAIN,
                            {CONF_NAME: DOMAIN, "config": cleaned_config},
                            cleaned_config,
                        )
                    )

        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["new_devices"] = False
        # prune stale devices
        device_registry = await dr.async_get_registry(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            for (_, identifier) in device_entry.identifiers:
                if identifier in hass.data[DATA_ALEXAMEDIA]["accounts"][email][
                    "devices"
                ]["media_player"].keys() or identifier in map(
                    lambda x: slugify(f"{x}_{email}"),
                    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"][
                        "media_player"
                    ].keys(),
                ):
                    break
            else:
                device_registry.async_remove_device(device_entry.id)
                _LOGGER.debug(
                    "%s: Removing stale device %s", hide_email(email), device_entry.name
                )

        await login_obj.save_cookiefile()
        if login_obj.access_token:
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_OAUTH: {
                        "access_token": login_obj.access_token,
                        "refresh_token": login_obj.refresh_token,
                        "expires_in": login_obj.expires_in,
                    },
                },
            )
        return entity_state

    @_catch_login_errors
    async def process_notifications(login_obj, raw_notifications=None):
        """Process raw notifications json."""
        if not raw_notifications:
            raw_notifications = await AlexaAPI.get_notifications(login_obj)
        email: Text = login_obj.email
        previous = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get(
            "notifications", {}
        )
        notifications = {"process_timestamp": dt.utcnow()}
        for notification in raw_notifications:
            n_dev_id = notification.get("deviceSerialNumber")
            if n_dev_id is None:
                # skip notifications untied to a device for now
                # https://github.com/custom-components/alexa_media_player/issues/633#issuecomment-610705651
                continue
            n_type = notification.get("type")
            if n_type is None:
                continue
            if n_type == "MusicAlarm":
                n_type = "Alarm"
            n_id = notification["notificationIndex"]
            if n_type == "Alarm":
                n_date = notification.get("originalDate")
                n_time = notification.get("originalTime")
                notification["date_time"] = (
                    f"{n_date} {n_time}" if n_date and n_time else None
                )
                previous_alarm = previous.get(n_dev_id, {}).get("Alarm", {}).get(n_id)
                if previous_alarm and alarm_just_dismissed(
                    notification,
                    previous_alarm.get("status"),
                    previous_alarm.get("version"),
                ):
                    hass.bus.async_fire(
                        "alexa_media_alarm_dismissal_event",
                        event_data={"device": {"id": n_dev_id}, "event": notification},
                    )

            if n_dev_id not in notifications:
                notifications[n_dev_id] = {}
            if n_type not in notifications[n_dev_id]:
                notifications[n_dev_id][n_type] = {}
            notifications[n_dev_id][n_type][n_id] = notification
        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["notifications"] = notifications
        _LOGGER.debug(
            "%s: Updated %s notifications for %s devices at %s",
            hide_email(email),
            len(raw_notifications),
            len(notifications),
            dt.as_local(
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["notifications"][
                    "process_timestamp"
                ]
            ),
        )

    @_catch_login_errors
    async def update_last_called(login_obj, last_called=None, force=False):
        """Update the last called device for the login_obj.

        This will store the last_called in hass.data and also fire an event
        to notify listeners.
        """
        if not last_called or not (last_called and last_called.get("summary")):
            try:
                last_called = await AlexaAPI.get_last_device_serial(login_obj)
            except TypeError:
                _LOGGER.debug(
                    "%s: Error updating last_called: %s",
                    hide_email(email),
                    hide_serial(last_called),
                )
                return
        _LOGGER.debug(
            "%s: Updated last_called: %s", hide_email(email), hide_serial(last_called)
        )
        stored_data = hass.data[DATA_ALEXAMEDIA]["accounts"][email]
        if (
            force
            or "last_called" in stored_data
            and last_called != stored_data["last_called"]
        ) or ("last_called" not in stored_data and last_called is not None):
            _LOGGER.debug(
                "%s: last_called changed: %s to %s",
                hide_email(email),
                hide_serial(
                    stored_data["last_called"] if "last_called" in stored_data else None
                ),
                hide_serial(last_called),
            )
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_{hide_email(email)}"[0:32],
                {"last_called_change": last_called},
            )
        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["last_called"] = last_called

    @_catch_login_errors
    async def update_bluetooth_state(login_obj, device_serial):
        """Update the bluetooth state on ws bluetooth event."""
        bluetooth = await AlexaAPI.get_bluetooth(login_obj)
        device = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["devices"][
            "media_player"
        ][device_serial]

        if "bluetoothStates" in bluetooth:
            for b_state in bluetooth["bluetoothStates"]:
                if device_serial == b_state["deviceSerialNumber"]:
                    # _LOGGER.debug("%s: setting value for: %s to %s",
                    #               hide_email(email),
                    #               hide_serial(device_serial),
                    #               hide_serial(b_state))
                    device["bluetooth_state"] = b_state
                    return device["bluetooth_state"]
        _LOGGER.debug(
            "%s: get_bluetooth for: %s failed with %s",
            hide_email(email),
            hide_serial(device_serial),
            hide_serial(bluetooth),
        )
        return None

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    @_catch_login_errors
    async def update_dnd_state(login_obj) -> None:
        """Update the dnd state on ws dnd combo event."""
        dnd = await AlexaAPI.get_dnd_state(login_obj)

        if "doNotDisturbDeviceStatusList" in dnd:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_{hide_email(email)}"[0:32],
                {"dnd_update": dnd["doNotDisturbDeviceStatusList"]},
            )
            return
        _LOGGER.debug("%s: get_dnd_state failed: dnd:%s", hide_email(email), dnd)
        return

    async def ws_connect() -> WebsocketEchoClient:
        """Open WebSocket connection.

        This will only attempt one login before failing.
        """
        websocket: Optional[WebsocketEchoClient] = None
        try:
            if login_obj.session.closed:
                _LOGGER.debug(
                    "%s: Websocket creation aborted. Session is closed.",
                    hide_email(email),
                )
                return
            websocket = WebsocketEchoClient(
                login_obj,
                ws_handler,
                ws_open_handler,
                ws_close_handler,
                ws_error_handler,
            )
            _LOGGER.debug("%s: Websocket created: %s", hide_email(email), websocket)
            await websocket.async_run()
        except BaseException as exception_:  # pylint: disable=broad-except
            _LOGGER.debug(
                "%s: Websocket creation failed: %s", hide_email(email), exception_
            )
            return
        return websocket

    async def ws_handler(message_obj):
        """Handle websocket messages.

        This allows push notifications from Alexa to update last_called
        and media state.
        """

        command = (
            message_obj.json_payload["command"]
            if isinstance(message_obj.json_payload, dict)
            and "command" in message_obj.json_payload
            else None
        )
        json_payload = (
            message_obj.json_payload["payload"]
            if isinstance(message_obj.json_payload, dict)
            and "payload" in message_obj.json_payload
            else None
        )
        existing_serials = _existing_serials(hass, login_obj)
        seen_commands = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "websocket_commands"
        ]
        coord = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["coordinator"]
        if command and json_payload:

            _LOGGER.debug(
                "%s: Received websocket command: %s : %s",
                hide_email(email),
                command,
                hide_serial(json_payload),
            )
            serial = None
            command_time = time.time()
            if command not in seen_commands:
                _LOGGER.debug("Adding %s to seen_commands: %s", command, seen_commands)
            seen_commands[command] = command_time

            if (
                "dopplerId" in json_payload
                and "deviceSerialNumber" in json_payload["dopplerId"]
            ):
                serial = json_payload["dopplerId"]["deviceSerialNumber"]
            elif (
                "key" in json_payload
                and "entryId" in json_payload["key"]
                and json_payload["key"]["entryId"].find("#") != -1
            ):
                serial = (json_payload["key"]["entryId"]).split("#")[2]
                json_payload["key"]["serialNumber"] = serial
            else:
                serial = None
            if command == "PUSH_ACTIVITY":
                #  Last_Alexa Updated
                last_called = {
                    "serialNumber": serial,
                    "timestamp": json_payload["timestamp"],
                }
                try:
                    await coord.async_request_refresh()
                    if serial and serial in existing_serials:
                        await update_last_called(login_obj, last_called)
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"push_activity": json_payload},
                    )
                except (AlexapyConnectionError):
                    # Catch case where activities doesn't report valid json
                    pass
            elif command in (
                "PUSH_AUDIO_PLAYER_STATE",
                "PUSH_MEDIA_CHANGE",
                "PUSH_MEDIA_PROGRESS_CHANGE",
            ):
                # Player update/ Push_media from tune_in
                if serial and serial in existing_serials:
                    _LOGGER.debug(
                        "Updating media_player: %s", hide_serial(json_payload)
                    )
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"player_state": json_payload},
                    )
            elif command == "PUSH_VOLUME_CHANGE":
                # Player volume update
                if serial and serial in existing_serials:
                    _LOGGER.debug(
                        "Updating media_player volume: %s", hide_serial(json_payload)
                    )
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"player_state": json_payload},
                    )
            elif command in (
                "PUSH_DOPPLER_CONNECTION_CHANGE",
                "PUSH_EQUALIZER_STATE_CHANGE",
            ):
                # Player availability update
                if serial and serial in existing_serials:
                    _LOGGER.debug(
                        "Updating media_player availability %s",
                        hide_serial(json_payload),
                    )
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"player_state": json_payload},
                    )
            elif command == "PUSH_BLUETOOTH_STATE_CHANGE":
                # Player bluetooth update
                bt_event = json_payload["bluetoothEvent"]
                bt_success = json_payload["bluetoothEventSuccess"]
                if (
                    serial
                    and serial in existing_serials
                    and bt_success
                    and bt_event
                    and bt_event in ["DEVICE_CONNECTED", "DEVICE_DISCONNECTED"]
                ):
                    _LOGGER.debug(
                        "Updating media_player bluetooth %s", hide_serial(json_payload)
                    )
                    bluetooth_state = await update_bluetooth_state(login_obj, serial)
                    # _LOGGER.debug("bluetooth_state %s",
                    #               hide_serial(bluetooth_state))
                    if bluetooth_state:
                        async_dispatcher_send(
                            hass,
                            f"{DOMAIN}_{hide_email(email)}"[0:32],
                            {"bluetooth_change": bluetooth_state},
                        )
            elif command == "PUSH_MEDIA_QUEUE_CHANGE":
                # Player availability update
                if serial and serial in existing_serials:
                    _LOGGER.debug(
                        "Updating media_player queue %s", hide_serial(json_payload)
                    )
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"queue_state": json_payload},
                    )
            elif command == "PUSH_NOTIFICATION_CHANGE":
                # Player update
                await process_notifications(login_obj)
                if serial and serial in existing_serials:
                    _LOGGER.debug(
                        "Updating mediaplayer notifications: %s",
                        hide_serial(json_payload),
                    )
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{hide_email(email)}"[0:32],
                        {"notification_update": json_payload},
                    )
            elif command in [
                "PUSH_DELETE_DOPPLER_ACTIVITIES",  # delete Alexa history
                "PUSH_LIST_CHANGE",  # clear a shopping list https://github.com/custom-components/alexa_media_player/issues/1190
                "PUSH_LIST_ITEM_CHANGE",  # update shopping list
                "PUSH_CONTENT_FOCUS_CHANGE",  # likely prime related refocus
                "PUSH_DEVICE_SETUP_STATE_CHANGE",  # likely device changes mid setup
            ]:
                pass
            else:
                _LOGGER.warning(
                    "Unhandled command: %s with data %s. Please report at %s",
                    command,
                    hide_serial(json_payload),
                    ISSUE_URL,
                )
            if serial in existing_serials:
                history = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
                    "websocket_activity"
                ]["serials"].get(serial)
                if history is None or (
                    history and command_time - history[len(history) - 1][1] > 2
                ):
                    history = [(command, command_time)]
                else:
                    history.append([command, command_time])
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocket_activity"][
                    "serials"
                ][serial] = history
                events = []
                for old_command, old_command_time in history:
                    if (
                        old_command
                        in {"PUSH_VOLUME_CHANGE", "PUSH_EQUALIZER_STATE_CHANGE"}
                        and command_time - old_command_time < 0.25
                    ):
                        events.append(
                            (old_command, round(command_time - old_command_time, 2))
                        )
                    elif old_command in {"PUSH_AUDIO_PLAYER_STATE"}:
                        # There is a potential false positive generated during this event
                        events = []
                if len(events) >= 4:
                    _LOGGER.debug(
                        "%s: Detected potential DND websocket change with %s events %s",
                        hide_serial(serial),
                        len(events),
                        events,
                    )
                    await update_dnd_state(login_obj)
            if (
                serial
                and serial not in existing_serials
                and serial
                not in (
                    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["excluded"].keys()
                )
            ):
                _LOGGER.debug("Discovered new media_player %s", serial)
                (hass.data[DATA_ALEXAMEDIA]["accounts"][email]["new_devices"]) = True
                coordinator = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get(
                    "coordinator"
                )
                if coordinator:
                    await coordinator.async_request_refresh()

    async def ws_open_handler():
        """Handle websocket open."""

        email: Text = login_obj.email
        _LOGGER.debug("%s: Websocket successfully connected", hide_email(email))
        hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "websocketerror"
        ] = 0  # set errors to 0
        hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "websocket_lastattempt"
        ] = time.time()

    async def ws_close_handler():
        """Handle websocket close.

        This should attempt to reconnect up to 5 times
        """

        email: Text = login_obj.email
        if login_obj.close_requested:
            _LOGGER.debug(
                "%s: Close requested; will not reconnect websocket", hide_email(email)
            )
            return
        if not login_obj.status.get("login_successful"):
            _LOGGER.debug(
                "%s: Login error; will not reconnect websocket", hide_email(email)
            )
            return
        errors: int = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"]
        delay: int = 5 * 2 ** errors
        last_attempt = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "websocket_lastattempt"
        ]
        now = time.time()
        if (now - last_attempt) < delay:
            return
        websocket_enabled: bool = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "websocket"
        ]
        while errors < 5 and not (websocket_enabled):
            _LOGGER.debug(
                "%s: Websocket closed; reconnect #%i in %is",
                hide_email(email),
                errors,
                delay,
            )
            hass.data[DATA_ALEXAMEDIA]["accounts"][email][
                "websocket_lastattempt"
            ] = time.time()
            websocket_enabled = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
                "websocket"
            ] = await ws_connect()
            errors = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"] = (
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"] + 1
            )
            delay = 5 * 2 ** errors
            errors = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"]
            await asyncio.sleep(delay)
        if not websocket_enabled:
            _LOGGER.debug(
                "%s: Websocket closed; retries exceeded; polling", hide_email(email)
            )
        coordinator = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get("coordinator")
        if coordinator:
            coordinator.update_interval = timedelta(
                seconds=scan_interval * 10 if websocket_enabled else scan_interval
            )
            await coordinator.async_request_refresh()

    async def ws_error_handler(message):
        """Handle websocket error.

        This currently logs the error.  In the future, this should invalidate
        the websocket and determine if a reconnect should be done. By
        specification, websockets will issue a close after every error.
        """
        email: Text = login_obj.email
        errors = hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"]
        _LOGGER.debug(
            "%s: Received websocket error #%i %s: type %s",
            hide_email(email),
            errors,
            message,
            type(message),
        )
        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocket"] = None
        if not login_obj.close_requested and (
            login_obj.session.closed or message == "<class 'aiohttp.streams.EofStream'>"
        ):
            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"] = 5
            _LOGGER.debug("%s: Immediate abort on EoFstream", hide_email(email))
            return
        hass.data[DATA_ALEXAMEDIA]["accounts"][email]["websocketerror"] = errors + 1

    _LOGGER.debug("Setting up Alexa devices for %s", hide_email(login_obj.email))
    config = config_entry.data
    email = config.get(CONF_EMAIL)
    include = config.get(CONF_INCLUDE_DEVICES)
    exclude = config.get(CONF_EXCLUDE_DEVICES)
    scan_interval: float = (
        config.get(CONF_SCAN_INTERVAL).total_seconds()
        if isinstance(config.get(CONF_SCAN_INTERVAL), timedelta)
        else config.get(CONF_SCAN_INTERVAL)
    )
    hass.data[DATA_ALEXAMEDIA]["accounts"][email]["login_obj"] = login_obj
    websocket_enabled = hass.data[DATA_ALEXAMEDIA]["accounts"][email][
        "websocket"
    ] = await ws_connect()
    coordinator = hass.data[DATA_ALEXAMEDIA]["accounts"][email].get("coordinator")
    if coordinator is None:
        _LOGGER.debug("%s: Creating coordinator", hide_email(email))
        hass.data[DATA_ALEXAMEDIA]["accounts"][email][
            "coordinator"
        ] = coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="alexa_media",
            update_method=async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(
                seconds=scan_interval * 10 if websocket_enabled else scan_interval
            ),
        )
    else:
        _LOGGER.debug("%s: Reusing coordinator", hide_email(email))
        coordinator.update_interval = timedelta(
            seconds=scan_interval * 10 if websocket_enabled else scan_interval
        )
    # Fetch initial data so we have data when entities subscribe
    _LOGGER.debug("%s: Refreshing coordinator", hide_email(email))
    await coordinator.async_refresh()

    hass.data[DATA_ALEXAMEDIA]["services"] = alexa_services = AlexaMediaServices(
        hass, functions={"update_last_called": update_last_called}
    )
    await alexa_services.register()
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    email = entry.data["email"]
    _LOGGER.debug("Attempting to unload entry for %s", hide_email(email))
    for component in ALEXA_COMPONENTS + DEPENDENT_ALEXA_COMPONENTS:
        _LOGGER.debug("Forwarding unload entry to %s", component)
        await hass.config_entries.async_forward_entry_unload(entry, component)
    # notify has to be handled manually as the forward does not work yet
    await notify_async_unload_entry(hass, entry)
    await close_connections(hass, email)
    for listener in hass.data[DATA_ALEXAMEDIA]["accounts"][email][DATA_LISTENER]:
        listener()
    hass.data[DATA_ALEXAMEDIA]["accounts"].pop(email)
    # Clean up config flows in progress
    flows_to_remove = []
    if hass.data[DATA_ALEXAMEDIA].get("config_flows"):
        for key, flow in hass.data[DATA_ALEXAMEDIA]["config_flows"].items():
            if key.startswith(email) and flow:
                _LOGGER.debug("Aborting flow %s %s", key, flow)
                flows_to_remove.append(key)
                try:
                    hass.config_entries.flow.async_abort(flow.get("flow_id"))
                except UnknownFlow:
                    pass
        for flow in flows_to_remove:
            hass.data[DATA_ALEXAMEDIA]["config_flows"].pop(flow)
    # Clean up hass.data
    if not hass.data[DATA_ALEXAMEDIA].get("accounts"):
        _LOGGER.debug("Removing accounts data and services")
        hass.data[DATA_ALEXAMEDIA].pop("accounts")
        alexa_services = hass.data[DATA_ALEXAMEDIA].get("services")
        if alexa_services:
            await alexa_services.unregister()
            hass.data[DATA_ALEXAMEDIA].pop("services")
    if hass.data[DATA_ALEXAMEDIA].get("config_flows") == {}:
        _LOGGER.debug("Removing config_flows data")
        hass.components.persistent_notification.async_dismiss(
            f"alexa_media_{slugify(email)}{slugify((entry.data['url'])[7:])}"
        )
        hass.data[DATA_ALEXAMEDIA].pop("config_flows")
    if not hass.data[DATA_ALEXAMEDIA]:
        _LOGGER.debug("Removing alexa_media data structure")
        if hass.data.get(DATA_ALEXAMEDIA):
            hass.data.pop(DATA_ALEXAMEDIA)
    else:
        _LOGGER.debug(
            "Unable to remove alexa_media data structure: %s",
            hass.data.get(DATA_ALEXAMEDIA),
        )
    _LOGGER.debug("Unloaded entry for %s", hide_email(email))
    return True


async def close_connections(hass, email: Text) -> None:
    """Clear open aiohttp connections for email."""
    if (
        email not in hass.data[DATA_ALEXAMEDIA]["accounts"]
        or "login_obj" not in hass.data[DATA_ALEXAMEDIA]["accounts"][email]
    ):
        return
    account_dict = hass.data[DATA_ALEXAMEDIA]["accounts"][email]
    login_obj = account_dict["login_obj"]
    await login_obj.save_cookiefile()
    await login_obj.close()
    _LOGGER.debug(
        "%s: Connection closed: %s", hide_email(email), login_obj.session.closed
    )


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    account = config_entry.data
    email = account.get(CONF_EMAIL)
    reload_needed: bool = False
    for key, old_value in hass.data[DATA_ALEXAMEDIA]["accounts"][email][
        "options"
    ].items():
        new_value = config_entry.options.get(key)
        if new_value is not None and new_value != old_value:
            hass.data[DATA_ALEXAMEDIA]["accounts"][email]["options"][key] = new_value
            _LOGGER.debug(
                "Changing option %s from %s to %s",
                key,
                old_value,
                hass.data[DATA_ALEXAMEDIA]["accounts"][email]["options"][key],
            )
            if key == CONF_EXTENDED_ENTITY_DISCOVERY:
                reload_needed = True
    if reload_needed:
        await hass.config_entries.async_reload(config_entry.entry_id)


async def test_login_status(hass, config_entry, login) -> bool:
    """Test the login status and spawn requests for info."""

    _LOGGER.debug("Testing login status: %s", login.status)
    if login.status and login.status.get("login_successful"):
        return True
    account = config_entry.data
    _LOGGER.debug("Logging in: %s %s", obfuscate(account), in_progess_instances(hass))
    _LOGGER.debug("Login stats: %s", login.stats)
    message: Text = f"Reauthenticate {login.email} on the [Integrations](/config/integrations) page. "
    if login.stats.get("login_timestamp") != datetime(1, 1, 1):
        elaspsed_time: str = str(datetime.now() - login.stats.get("login_timestamp"))
        api_calls: int = login.stats.get("api_calls")
        message += f"Relogin required after {elaspsed_time} and {api_calls} api calls."
    hass.components.persistent_notification.async_create(
        title="Alexa Media Reauthentication Required",
        message=message,
        notification_id=f"alexa_media_{slugify(login.email)}{slugify(login.url[7:])}",
    )
    flow = hass.data[DATA_ALEXAMEDIA]["config_flows"].get(
        f"{account[CONF_EMAIL]} - {account[CONF_URL]}"
    )
    if flow:
        if flow.get("flow_id") in in_progess_instances(hass):
            _LOGGER.debug("Existing config flow detected")
            return False
        _LOGGER.debug("Stopping orphaned config flow %s", flow.get("flow_id"))
        try:
            hass.config_entries.flow.async_abort(flow.get("flow_id"))
        except UnknownFlow:
            pass
        hass.data[DATA_ALEXAMEDIA]["config_flows"][
            f"{account[CONF_EMAIL]} - {account[CONF_URL]}"
        ] = None
    _LOGGER.debug("Creating new config flow to login")
    hass.data[DATA_ALEXAMEDIA]["config_flows"][
        f"{account[CONF_EMAIL]} - {account[CONF_URL]}"
    ] = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth"},
        data={
            CONF_EMAIL: account[CONF_EMAIL],
            CONF_PASSWORD: account[CONF_PASSWORD],
            CONF_URL: account[CONF_URL],
            CONF_DEBUG: account[CONF_DEBUG],
            CONF_INCLUDE_DEVICES: account[CONF_INCLUDE_DEVICES],
            CONF_EXCLUDE_DEVICES: account[CONF_EXCLUDE_DEVICES],
            CONF_SCAN_INTERVAL: account[CONF_SCAN_INTERVAL].total_seconds()
            if isinstance(account[CONF_SCAN_INTERVAL], timedelta)
            else account[CONF_SCAN_INTERVAL],
            CONF_COOKIES_TXT: account.get(CONF_COOKIES_TXT, ""),
            CONF_OTPSECRET: account.get(CONF_OTPSECRET, ""),
        },
    )
    return False

"""Support for Huawei LTE routers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any, NamedTuple, cast
from xml.parsers.expat import ExpatError

from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.exceptions import (
    LoginErrorInvalidCredentialsException,
    ResponseErrorException,
    ResponseErrorLoginRequiredException,
    ResponseErrorNotSupportedException,
)
from requests.exceptions import Timeout
import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADMIN_SERVICES,
    ALL_KEYS,
    ATTR_CONFIG_ENTRY_ID,
    CONF_MANUFACTURER,
    CONF_UNAUTHENTICATED_MODE,
    CONNECTION_TIMEOUT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_MANUFACTURER,
    DEFAULT_NOTIFY_SERVICE_NAME,
    DOMAIN,
    KEY_DEVICE_BASIC_INFORMATION,
    KEY_DEVICE_INFORMATION,
    KEY_DEVICE_SIGNAL,
    KEY_DIALUP_MOBILE_DATASWITCH,
    KEY_LAN_HOST_INFO,
    KEY_MONITORING_CHECK_NOTIFICATIONS,
    KEY_MONITORING_MONTH_STATISTICS,
    KEY_MONITORING_STATUS,
    KEY_MONITORING_TRAFFIC_STATISTICS,
    KEY_NET_CURRENT_PLMN,
    KEY_NET_NET_MODE,
    KEY_SMS_SMS_COUNT,
    KEY_WLAN_HOST_LIST,
    KEY_WLAN_WIFI_FEATURE_SWITCH,
    KEY_WLAN_WIFI_GUEST_NETWORK_SWITCH,
    NOTIFY_SUPPRESS_TIMEOUT,
    SERVICE_RESUME_INTEGRATION,
    SERVICE_SUSPEND_INTEGRATION,
    UPDATE_SIGNAL,
)
from .utils import get_device_macs, non_verifying_requests_session

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

NOTIFY_SCHEMA = vol.Any(
    None,
    vol.Schema(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_RECIPIENT): vol.Any(
                None, vol.All(cv.ensure_list, [cv.string])
            ),
        }
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_URL): cv.url,
                        vol.Optional(CONF_USERNAME): cv.string,
                        vol.Optional(CONF_PASSWORD): cv.string,
                        vol.Optional(NOTIFY_DOMAIN): NOTIFY_SCHEMA,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema({vol.Optional(CONF_URL): cv.url})

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class Router:
    """Class for router state."""

    hass: HomeAssistant
    config_entry: ConfigEntry
    connection: Connection
    url: str

    data: dict[str, Any] = field(default_factory=dict, init=False)
    # Values are lists rather than sets, because the same item may be used by more than
    # one thing, such as MonthDuration for CurrentMonth{Download,Upload}.
    subscriptions: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(
            list, ((x, ["initial_scan"]) for x in ALL_KEYS)
        ),
        init=False,
    )
    inflight_gets: set[str] = field(default_factory=set, init=False)
    client: Client = field(init=False)
    suspended: bool = field(default=False, init=False)
    notify_last_attempt: float = field(default=-1, init=False)

    def __post_init__(self) -> None:
        """Set up internal state on init."""
        self.client = Client(self.connection)

    @property
    def device_name(self) -> str:
        """Get router device name."""
        for key, item in (
            (KEY_DEVICE_BASIC_INFORMATION, "devicename"),
            (KEY_DEVICE_INFORMATION, "DeviceName"),
        ):
            with suppress(KeyError, TypeError):
                return cast(str, self.data[key][item])
        return DEFAULT_DEVICE_NAME

    @property
    def device_identifiers(self) -> set[tuple[str, str]]:
        """Get router identifiers for device registry."""
        assert self.config_entry.unique_id is not None
        return {(DOMAIN, self.config_entry.unique_id)}

    @property
    def device_connections(self) -> set[tuple[str, str]]:
        """Get router connections for device registry."""
        return {
            (dr.CONNECTION_NETWORK_MAC, x) for x in self.config_entry.data[CONF_MAC]
        }

    def _get_data(self, key: str, func: Callable[[], Any]) -> None:
        if not self.subscriptions.get(key):
            return
        if key in self.inflight_gets:
            _LOGGER.debug("Skipping already in-flight get for %s", key)
            return
        self.inflight_gets.add(key)
        _LOGGER.debug("Getting %s for subscribers %s", key, self.subscriptions[key])
        try:
            self.data[key] = func()
        except ResponseErrorLoginRequiredException:
            if not self.config_entry.options.get(CONF_UNAUTHENTICATED_MODE):
                _LOGGER.debug("Trying to authorize again")
                if self.client.user.login(
                    self.config_entry.data.get(CONF_USERNAME, ""),
                    self.config_entry.data.get(CONF_PASSWORD, ""),
                ):
                    _LOGGER.debug(
                        "success, %s will be updated by a future periodic run",
                        key,
                    )
                else:
                    _LOGGER.debug("failed")
                return
            _LOGGER.info(
                "%s requires authorization, excluding from future updates", key
            )
            self.subscriptions.pop(key)
        except (ResponseErrorException, ExpatError) as exc:
            # Take ResponseErrorNotSupportedException, ExpatError, and generic
            # ResponseErrorException with a few select codes to mean the endpoint is
            # not supported.
            if not isinstance(
                exc, (ResponseErrorNotSupportedException, ExpatError)
            ) and exc.code not in (-1, 100006):
                raise
            _LOGGER.info(
                "%s apparently not supported by device, excluding from future updates",
                key,
            )
            self.subscriptions.pop(key)
        except Timeout:
            grace_left = (
                self.notify_last_attempt - time.monotonic() + NOTIFY_SUPPRESS_TIMEOUT
            )
            if grace_left > 0:
                _LOGGER.debug(
                    "%s timed out, %.1fs notify timeout suppress grace remaining",
                    key,
                    grace_left,
                    exc_info=True,
                )
            else:
                raise
        finally:
            self.inflight_gets.discard(key)
            _LOGGER.debug("%s=%s", key, self.data.get(key))

    def update(self) -> None:
        """Update router data."""

        if self.suspended:
            _LOGGER.debug("Integration suspended, not updating data")
            return

        self._get_data(KEY_DEVICE_INFORMATION, self.client.device.information)
        if self.data.get(KEY_DEVICE_INFORMATION):
            # Full information includes everything in basic
            self.subscriptions.pop(KEY_DEVICE_BASIC_INFORMATION, None)
        self._get_data(
            KEY_DEVICE_BASIC_INFORMATION, self.client.device.basic_information
        )
        self._get_data(KEY_DEVICE_SIGNAL, self.client.device.signal)
        self._get_data(
            KEY_DIALUP_MOBILE_DATASWITCH, self.client.dial_up.mobile_dataswitch
        )
        self._get_data(
            KEY_MONITORING_MONTH_STATISTICS, self.client.monitoring.month_statistics
        )
        self._get_data(
            KEY_MONITORING_CHECK_NOTIFICATIONS,
            self.client.monitoring.check_notifications,
        )
        self._get_data(KEY_MONITORING_STATUS, self.client.monitoring.status)
        self._get_data(
            KEY_MONITORING_TRAFFIC_STATISTICS, self.client.monitoring.traffic_statistics
        )
        self._get_data(KEY_NET_CURRENT_PLMN, self.client.net.current_plmn)
        self._get_data(KEY_NET_NET_MODE, self.client.net.net_mode)
        self._get_data(KEY_SMS_SMS_COUNT, self.client.sms.sms_count)
        self._get_data(KEY_LAN_HOST_INFO, self.client.lan.host_info)
        if self.data.get(KEY_LAN_HOST_INFO):
            # LAN host info includes everything in WLAN host list
            self.subscriptions.pop(KEY_WLAN_HOST_LIST, None)
        self._get_data(KEY_WLAN_HOST_LIST, self.client.wlan.host_list)
        self._get_data(
            KEY_WLAN_WIFI_FEATURE_SWITCH, self.client.wlan.wifi_feature_switch
        )
        self._get_data(
            KEY_WLAN_WIFI_GUEST_NETWORK_SWITCH,
            lambda: next(
                (
                    ssid
                    for ssid in self.client.wlan.multi_basic_settings()
                    .get("Ssids", {})
                    .get("Ssid", [])
                    if isinstance(ssid, dict) and ssid.get("wifiisguestnetwork") == "1"
                ),
                {},
            ),
        )

        dispatcher_send(self.hass, UPDATE_SIGNAL, self.config_entry.unique_id)

    def logout(self) -> None:
        """Log out router session."""
        try:
            self.client.user.logout()
        except (
            ResponseErrorLoginRequiredException,
            ResponseErrorNotSupportedException,
        ):
            pass  # Ok, normal, nothing to do
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Logout error", exc_info=True)

    def cleanup(self, *_: Any) -> None:
        """Clean up resources."""

        self.subscriptions.clear()

        self.logout()
        self.connection.requests_session.close()


class HuaweiLteData(NamedTuple):
    """Shared state."""

    hass_config: ConfigType
    routers: dict[str, Router]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huawei LTE component from config entry."""
    url = entry.data[CONF_URL]

    def _connect() -> Connection:
        """Set up a connection."""
        kwargs: dict[str, Any] = {
            "timeout": CONNECTION_TIMEOUT,
        }
        if url.startswith("https://") and not entry.data.get(CONF_VERIFY_SSL):
            kwargs["requests_session"] = non_verifying_requests_session(url)
        if entry.options.get(CONF_UNAUTHENTICATED_MODE):
            _LOGGER.debug("Connecting in unauthenticated mode, reduced feature set")
            connection = Connection(url, **kwargs)
        else:
            _LOGGER.debug("Connecting in authenticated mode, full feature set")
            username = entry.data.get(CONF_USERNAME) or ""
            password = entry.data.get(CONF_PASSWORD) or ""
            connection = Connection(url, username=username, password=password, **kwargs)
        return connection

    try:
        connection = await hass.async_add_executor_job(_connect)
    except LoginErrorInvalidCredentialsException as ex:
        raise ConfigEntryAuthFailed from ex
    except Timeout as ex:
        raise ConfigEntryNotReady from ex

    # Set up router
    router = Router(hass, entry, connection, url)

    # Do initial data update
    await hass.async_add_executor_job(router.update)

    # Check that we found required information
    router_info = router.data.get(KEY_DEVICE_INFORMATION)
    if not entry.unique_id:
        # Transitional from < 2021.8: update None config entry and entity unique ids
        if router_info and (serial_number := router_info.get("SerialNumber")):
            hass.config_entries.async_update_entry(entry, unique_id=serial_number)
            ent_reg = er.async_get(hass)
            for entity_entry in er.async_entries_for_config_entry(
                ent_reg, entry.entry_id
            ):
                if not entity_entry.unique_id.startswith("None-"):
                    continue
                new_unique_id = entity_entry.unique_id.removeprefix("None-")
                new_unique_id = f"{serial_number}-{new_unique_id}"
                ent_reg.async_update_entity(
                    entity_entry.entity_id, new_unique_id=new_unique_id
                )
        else:
            await hass.async_add_executor_job(router.cleanup)
            msg = (
                "Could not resolve serial number to use as unique id for router at %s"
                ", setup failed"
            )
            if not entry.data.get(CONF_PASSWORD):
                msg += (
                    ". Try setting up credentials for the router for one startup, "
                    "unauthenticated mode can be enabled after that in integration "
                    "settings"
                )
            _LOGGER.error(msg, url)
            return False

    # Store reference to router
    hass.data[DOMAIN].routers[entry.entry_id] = router

    # Clear all subscriptions, enabled entities will push back theirs
    router.subscriptions.clear()

    # Update device MAC addresses on record. These can change due to toggling between
    # authenticated and unauthenticated modes, or likely also when enabling/disabling
    # SSIDs in the router config.
    try:
        wlan_settings = await hass.async_add_executor_job(
            router.client.wlan.multi_basic_settings
        )
    except Exception:  # noqa: BLE001
        # Assume not supported, or authentication required but in unauthenticated mode
        wlan_settings = {}
    macs = get_device_macs(router_info or {}, wlan_settings)
    # Be careful not to overwrite a previous, more complete set with a partial one
    if macs and (not entry.data[CONF_MAC] or (router_info and wlan_settings)):
        new_data = dict(entry.data)
        new_data[CONF_MAC] = macs
        hass.config_entries.async_update_entry(entry, data=new_data)

    # Set up device registry
    if router.device_identifiers or router.device_connections:
        device_info = DeviceInfo(
            configuration_url=router.url,
            connections=router.device_connections,
            identifiers=router.device_identifiers,
            manufacturer=entry.data.get(CONF_MANUFACTURER, DEFAULT_MANUFACTURER),
            name=router.device_name,
        )
        hw_version = None
        sw_version = None
        if router_info:
            hw_version = router_info.get("HardwareVersion")
            sw_version = router_info.get("SoftwareVersion")
            if router_info.get("DeviceName"):
                device_info[ATTR_MODEL] = router_info["DeviceName"]
        if not sw_version and router.data.get(KEY_DEVICE_BASIC_INFORMATION):
            sw_version = router.data[KEY_DEVICE_BASIC_INFORMATION].get(
                "SoftwareVersion"
            )
        if hw_version:
            device_info[ATTR_HW_VERSION] = hw_version
        if sw_version:
            device_info[ATTR_SW_VERSION] = sw_version
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **device_info,
        )

    # Forward config entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Notify doesn't support config entry setup yet, load with discovery for now
    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            CONF_NAME: entry.options.get(CONF_NAME, DEFAULT_NOTIFY_SERVICE_NAME),
            CONF_RECIPIENT: entry.options.get(CONF_RECIPIENT),
        },
        hass.data[DOMAIN].hass_config,
    )

    def _update_router(*_: Any) -> None:
        """Update router data.

        Separate passthrough function because lambdas don't work with track_time_interval.
        """
        router.update()

    # Set up periodic update
    entry.async_on_unload(
        async_track_time_interval(hass, _update_router, SCAN_INTERVAL)
    )

    # Clean up at end
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, router.cleanup)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload config entry."""

    # Forward config entry unload to platforms
    await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    # Forget about the router and invoke its cleanup
    router = hass.data[DOMAIN].routers.pop(config_entry.entry_id)
    await hass.async_add_executor_job(router.cleanup)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Huawei LTE component."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = HuaweiLteData(hass_config=config, routers={})

    def service_handler(service: ServiceCall) -> None:
        """Apply a service.

        We key this using the router URL instead of its unique id / serial number,
        because the latter is not available anywhere in the UI.
        """
        routers = hass.data[DOMAIN].routers
        if url := service.data.get(CONF_URL):
            router = next(
                (router for router in routers.values() if router.url == url), None
            )
        elif not routers:
            _LOGGER.error("%s: no routers configured", service.service)
            return
        elif len(routers) == 1:
            router = next(iter(routers.values()))
        else:
            _LOGGER.error(
                "%s: more than one router configured, must specify one of URLs %s",
                service.service,
                sorted(router.url for router in routers.values()),
            )
            return
        if not router:
            _LOGGER.error("%s: router %s unavailable", service.service, url)
            return

        if service.service == SERVICE_RESUME_INTEGRATION:
            # Login will be handled automatically on demand
            router.suspended = False
            _LOGGER.debug("%s: %s", service.service, "done")
        elif service.service == SERVICE_SUSPEND_INTEGRATION:
            router.logout()
            router.suspended = True
            _LOGGER.debug("%s: %s", service.service, "done")
        else:
            _LOGGER.error("%s: unsupported service", service.service)

    for service in ADMIN_SERVICES:
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            service_handler,
            schema=SERVICE_SCHEMA,
        )

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry to new version."""
    if config_entry.version == 1:
        options = dict(config_entry.options)
        recipient = options.get(CONF_RECIPIENT)
        if isinstance(recipient, str):
            options[CONF_RECIPIENT] = [x.strip() for x in recipient.split(",")]
        hass.config_entries.async_update_entry(config_entry, options=options, version=2)
        _LOGGER.info("Migrated config entry to version %d", config_entry.version)
    if config_entry.version == 2:
        data = dict(config_entry.data)
        data[CONF_MAC] = []
        hass.config_entries.async_update_entry(config_entry, data=data, version=3)
        _LOGGER.info("Migrated config entry to version %d", config_entry.version)
    # There can be no longer needed *_from_yaml data and options things left behind
    # from pre-2022.4ish; they can be removed while at it when/if we eventually bump and
    # migrate to version > 3 for some other reason.
    return True


class HuaweiLteBaseEntity(Entity):
    """Huawei LTE entity base class."""

    _available = True
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, router: Router) -> None:
        """Initialize."""
        self.router = router
        self._unsub_handlers: list[Callable] = []

    @property
    def _device_unique_id(self) -> str:
        """Return unique ID for entity within a router."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"{self.router.config_entry.unique_id}-{self._device_unique_id}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update state."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Connect to update signals."""
        self._unsub_handlers.append(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self._async_maybe_update)
        )

    async def _async_maybe_update(self, config_entry_unique_id: str) -> None:
        """Update state if the update signal comes from our router."""
        if config_entry_unique_id == self.router.config_entry.unique_id:
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Invoke unsubscription handlers."""
        for unsub in self._unsub_handlers:
            unsub()
        self._unsub_handlers.clear()


class HuaweiLteBaseEntityWithDevice(HuaweiLteBaseEntity):
    """Base entity with device info."""

    @property
    def device_info(self) -> DeviceInfo:
        """Get info for matching with parent router."""
        return DeviceInfo(
            connections=self.router.device_connections,
            identifiers=self.router.device_identifiers,
        )

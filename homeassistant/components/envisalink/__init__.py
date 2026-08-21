"""Support for Envisalink devices."""

import asyncio
import logging

from pyenvisalink import EnvisalinkAlarmPanel
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CUSTOM_FUNCTION,
    ATTR_PARTITION,
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONENAME,
    CONF_ZONES,
    CONF_ZONETYPE,
    DEFAULT_EVL_VERSION,
    DEFAULT_KEEPALIVE,
    DEFAULT_PANIC,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    DEFAULT_ZONETYPE,
    DOMAIN,
    LOGIN_RESPONSE_TIMEOUT,
    PANEL_TYPE_DSC,
    PANEL_TYPE_HONEYWELL,
    PLATFORMS,
    SERVICE_CUSTOM_FUNCTION,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SIGNAL_ZONE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

type EnvisalinkConfigEntry = ConfigEntry[EnvisalinkAlarmPanel]

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONENAME): cv.string,
        vol.Optional(CONF_ZONETYPE, default=DEFAULT_ZONETYPE): cv.string,
    }
)

PARTITION_SCHEMA = vol.Schema({vol.Required(CONF_PARTITIONNAME): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PANEL_TYPE): vol.All(
                    cv.string, vol.In([PANEL_TYPE_HONEYWELL, PANEL_TYPE_DSC])
                ),
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASS): cv.string,
                vol.Optional(CONF_CODE): cv.string,
                vol.Optional(CONF_PANIC, default=DEFAULT_PANIC): cv.string,
                vol.Optional(CONF_ZONES): {vol.Coerce(int): ZONE_SCHEMA},
                vol.Optional(CONF_PARTITIONS): {vol.Coerce(int): PARTITION_SCHEMA},
                vol.Optional(CONF_EVL_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_EVL_VERSION, default=DEFAULT_EVL_VERSION): vol.All(
                    vol.Coerce(int), vol.Range(min=3, max=4)
                ),
                # keepalive_interval, zonedump_interval and timeout are no longer
                # user-configurable; accepted here only so existing YAML doesn't
                # hard-error, and ignored on import.
                vol.Optional("keepalive_interval"): vol.All(
                    vol.Coerce(int), vol.Range(min=15)
                ),
                vol.Optional("zonedump_interval"): vol.Coerce(int),
                vol.Optional(CONF_TIMEOUT): vol.Coerce(int),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        vol.Required(ATTR_PARTITION): cv.string,
    }
)


class InvalidAuth(Exception):
    """Error to indicate the panel rejected our credentials."""


class LoginTimeout(Exception):
    """Error to indicate no login response was ever recognized.

    Distinct from pyenvisalink's own tolerate-and-retry timeout (returned as
    login_succeeded=False, controller left running): this is our outer bound
    giving up entirely, after which the panel has already been disconnected
    and cannot self-heal.
    """


def disconnect_panel(controller: EnvisalinkAlarmPanel) -> None:
    """Force-close a panel connection and cancel any pending reconnect.

    pyenvisalink's own stop() only sets an internal shutdown flag when given
    an external event loop (always true for us) - it never closes the
    transport. Worse, a reconnect already scheduled before stop() is called
    fires anyway once its delay elapses: reconnect() doesn't check that flag
    before reconnecting. Left alone, a failed/cancelled/timed-out connection
    attempt (e.g. during config flow validation) keeps a background
    reconnect loop alive indefinitely. This reaches past stop() to force an
    immediate, complete teardown instead.
    """
    controller.stop()
    controller._client.disconnect()  # noqa: SLF001
    if (reconnect_task := controller._client._reconnect_task) is not None:  # noqa: SLF001
        reconnect_task.cancel()


async def async_connect_panel(
    hass: HomeAssistant,
    host: str,
    port: int,
    panel_type: str,
    version: int,
    user: str,
    password: str,
    zone_dump: int = DEFAULT_ZONEDUMP_INTERVAL,
    keep_alive: int = DEFAULT_KEEPALIVE,
    connection_timeout: int | None = None,
) -> tuple[EnvisalinkAlarmPanel, bool]:
    """Start a connection to an Envisalink panel and wait for a login result.

    Returns (controller, login_succeeded). login_succeeded is False when the
    login attempt timed out at the library level; pyenvisalink keeps
    retrying in the background in that case, so the controller is still
    returned running. Raises InvalidAuth if the panel rejects the given
    credentials.

    pyenvisalink's own connection_timeout only bounds the raw TCP connect: if
    the panel never sends a response the library recognizes as a login
    success/failure (e.g. the wrong panel_type was selected, so its parser
    can't make sense of the panel's replies), none of the login callbacks
    ever fire and the connection attempt would otherwise hang forever. The
    asyncio.timeout below bounds the whole wait, on top of that - unlike the
    library's own timeout, giving up here means the panel is disconnected
    and can't self-heal, so it's raised as LoginTimeout instead of returned.
    """
    # connection_timeout is resolved here rather than defaulted in the
    # signature so tests can shrink DEFAULT_TIMEOUT via patch() even when
    # calling through async_setup_entry/_async_test_connection, which don't
    # expose their own connection_timeout override.
    if connection_timeout is None:
        connection_timeout = DEFAULT_TIMEOUT

    sync_connect: asyncio.Future[bool] = hass.loop.create_future()

    controller = EnvisalinkAlarmPanel(
        host,
        port,
        panel_type,
        version,
        user,
        password,
        zone_dump,
        keep_alive,
        hass.loop,
        connection_timeout,
        False,
    )

    @callback
    def async_login_fail_callback(data):
        """Handle when the evl rejects our login."""
        _LOGGER.error("The Envisalink rejected your credentials")
        if not sync_connect.done():
            sync_connect.set_exception(InvalidAuth)

    @callback
    def async_connection_fail_callback(data):
        """Network failure callback."""
        _LOGGER.error("Could not establish a connection with the Envisalink- retrying")
        if not sync_connect.done():
            sync_connect.set_result(False)

    @callback
    def async_connection_success_callback(data):
        """Handle a successful connection."""
        _LOGGER.debug("Established a connection with the Envisalink")
        if not sync_connect.done():
            sync_connect.set_result(True)

    @callback
    def async_zones_updated_callback(data):
        """Handle zone timer updates."""
        _LOGGER.debug("Envisalink sent a zone update event. Updating zones")
        async_dispatcher_send(hass, SIGNAL_ZONE_UPDATE, data)

    @callback
    def async_alarm_data_updated_callback(data):
        """Handle non-alarm based info updates."""
        _LOGGER.debug("Envisalink sent new alarm info. Updating alarms")
        async_dispatcher_send(hass, SIGNAL_KEYPAD_UPDATE, data)

    @callback
    def async_partition_updated_callback(data):
        """Handle partition changes thrown by evl (including alarms)."""
        _LOGGER.debug("The envisalink sent a partition update event")
        async_dispatcher_send(hass, SIGNAL_PARTITION_UPDATE, data)

    # All callbacks must be wired up before start(), since the panel can send
    # an initial zone/partition/keypad status dump immediately after login
    # succeeds, in the same synchronous burst as the login response.
    controller.callback_login_failure = async_login_fail_callback
    controller.callback_login_timeout = async_connection_fail_callback
    controller.callback_login_success = async_connection_success_callback
    controller.callback_zone_timer_dump = async_zones_updated_callback
    controller.callback_zone_state_change = async_zones_updated_callback
    controller.callback_partition_state_change = async_partition_updated_callback
    controller.callback_keypad_update = async_alarm_data_updated_callback

    try:
        _LOGGER.debug("Start envisalink")
        controller.start()
        async with asyncio.timeout(connection_timeout + LOGIN_RESPONSE_TIMEOUT):
            login_succeeded = await sync_connect
    except asyncio.CancelledError:
        # If we're cancelled before the connection resolves (e.g. the config
        # flow using us is aborted mid-connect), disconnect_panel() must
        # still run, or the connection (and its background reconnect) keeps
        # running forever on an orphaned, unreferenced panel.
        disconnect_panel(controller)
        raise
    except TimeoutError as err:
        disconnect_panel(controller)
        raise LoginTimeout from err
    except Exception:
        # Covers InvalidAuth and any other unexpected error - always leave
        # the panel fully torn down rather than running unreferenced.
        disconnect_panel(controller)
        raise

    return controller, login_succeeded


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Envisalink component."""

    async def handle_custom_function(call: ServiceCall) -> None:
        """Handle custom/PGM service."""
        entry = next(iter(hass.config_entries.async_loaded_entries(DOMAIN)), None)
        if entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_loaded_entry",
            )
        custom_function = call.data[ATTR_CUSTOM_FUNCTION]
        partition = call.data[ATTR_PARTITION]
        entry.runtime_data.command_output(
            entry.options.get(CONF_CODE), partition, custom_function
        )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_CUSTOM_FUNCTION, handle_custom_function, SERVICE_SCHEMA
    )

    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_import(hass, config[DOMAIN]))
    return True


async def _async_import(hass: HomeAssistant, conf: ConfigType) -> None:
    """Import Envisalink configuration from YAML and surface appropriate issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2027.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Envisalink",
                **(result.get("description_placeholders") or {}),
            },
        )
        return

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Envisalink",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: EnvisalinkConfigEntry) -> bool:
    """Set up Envisalink from a config entry."""
    try:
        controller, _ = await async_connect_panel(
            hass,
            entry.data[CONF_HOST],
            entry.data[CONF_EVL_PORT],
            entry.data[CONF_PANEL_TYPE],
            entry.data[CONF_EVL_VERSION],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASS],
        )
    except InvalidAuth:
        return False
    except LoginTimeout as err:
        raise ConfigEntryNotReady(
            f"Timed out waiting for a login response from {entry.data[CONF_HOST]}"
        ) from err

    entry.runtime_data = controller

    @callback
    def stop_envisalink(event) -> None:
        """Shutdown envisalink connection and thread on exit."""
        _LOGGER.debug("Shutting down Envisalink")
        disconnect_panel(controller)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_envisalink)
    )

    # Adding/editing a zone or partition subentry doesn't reload the
    # entry on its own (only reconfiguring the main connection does) -
    # without this, newly added zones/partitions wouldn't create
    # entities until restart.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except asyncio.CancelledError, Exception:
        # Failed setup does not call async_unload_entry, so disconnect explicitly.
        disconnect_panel(controller)
        raise

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: EnvisalinkConfigEntry
) -> None:
    """Reload the entry when its data, options or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EnvisalinkConfigEntry) -> bool:
    """Unload an Envisalink config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        disconnect_panel(entry.runtime_data)
    return unload_ok

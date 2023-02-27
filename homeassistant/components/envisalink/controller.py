"""Support for Envisalink devices."""
from collections.abc import Callable

from pyenvisalink.alarm_panel import EnvisalinkAlarmPanel
from pyenvisalink.const import (
    STATE_CHANGE_PARTITION,
    STATE_CHANGE_ZONE,
    STATE_CHANGE_ZONE_BYPASS,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TIMEOUT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_EVL_DISCOVERY_PORT,
    CONF_EVL_KEEPALIVE,
    CONF_EVL_PORT,
    CONF_PASS,
    CONF_USERNAME,
    CONF_ZONEDUMP_INTERVAL,
    DEFAULT_CREATE_ZONE_BYPASS_SWITCHES,
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_KEEPALIVE,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_ZONEDUMP_INTERVAL,
    LOGGER,
)


class EnvisalinkController:
    """Controller class for managing interactions with the underlying Envisalink device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the controller for the Envisalink device."""
        self._unique_id = entry.unique_id

        # Config
        self.alarm_name = entry.title
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_EVL_PORT, DEFAULT_PORT)
        discovery_port = entry.data.get(CONF_EVL_DISCOVERY_PORT, DEFAULT_DISCOVERY_PORT)
        user = entry.data.get(CONF_USERNAME)
        password = str(entry.data.get(CONF_PASS))

        # Options
        keep_alive = entry.options.get(CONF_EVL_KEEPALIVE, DEFAULT_KEEPALIVE)
        zone_dump = entry.options.get(CONF_ZONEDUMP_INTERVAL, DEFAULT_ZONEDUMP_INTERVAL)
        create_zone_bypass_switches = entry.options.get(
            CONF_CREATE_ZONE_BYPASS_SWITCHES, DEFAULT_CREATE_ZONE_BYPASS_SWITCHES
        )
        connection_timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        self.hass = hass

        self.controller = EnvisalinkAlarmPanel(
            host,
            port,
            user,
            password,
            zone_dump,
            keep_alive,
            connection_timeout,
            create_zone_bypass_switches,
            httpPort=discovery_port,
        )

        self._listeners: dict[str, dict] = {
            STATE_CHANGE_PARTITION: {},
            STATE_CHANGE_ZONE: {},
            STATE_CHANGE_ZONE_BYPASS: {},
        }

        self.controller.callback_connection_status = (
            self.async_connection_status_callback
        )
        self.controller.callback_login_failure = self.async_login_fail_callback
        self.controller.callback_login_timeout = self.async_login_timeout_callback
        self.controller.callback_login_success = self.async_login_success_callback

        self.controller.callback_keypad_update = self.async_keypad_updated_callback
        self.controller.callback_zone_state_change = self.async_zones_updated_callback
        self.controller.callback_zone_bypass_state_change = (
            self.async_zone_bypass_update
        )
        self.controller.callback_partition_state_change = (
            self.async_partition_updated_callback
        )

        LOGGER.debug(
            "Created EnvisalinkController for %s (host=%s port=%r)",
            self.alarm_name,
            host,
            port,
        )

    def add_state_change_listener(
        self, state_type, state_key, update_callback
    ) -> Callable[[], None]:
        """Register an entity to have a state update triggered when it's underlying data is changed."""

        def remove_listener() -> None:
            for state_types in self._listeners.values():
                for key_list in state_types.values():
                    for idx, listener in enumerate(key_list):
                        # pylint: disable-next=comparison-with-callable
                        if listener[0] == remove_listener:
                            key_list.pop(idx)
                            break

        state_info = self._listeners[state_type]
        if state_key not in state_info:
            state_info[state_key] = []
        state_info[state_key].append((remove_listener, update_callback))
        return remove_listener

    def _process_state_change(self, update_type: str, update_keys: list):
        state_info = self._listeners[update_type]
        for key in update_keys:
            if key in state_info:
                for listener in state_info[key]:
                    listener[1]()

    def _update_entity_states(self):
        """Trigger a state update for all entities."""
        for state_info in self._listeners.values():
            for key_list in state_info.values():
                for listener in key_list:
                    listener[1]()

    @property
    def unique_id(self):
        """Return the unique ID of the underlying device."""
        return self._unique_id

    async def start(self) -> bool:
        """Start and connection to the underlying Envisalink alarm panel device."""
        LOGGER.info("Start envisalink")
        await self.controller.discover()

        if self.controller.mac_address:
            mac = format_mac(self.controller.mac_address)
            if mac != self._unique_id:
                LOGGER.warning(
                    (
                        "MAC address (%s) of EVL device (%s) does not match "
                        "unique ID (%s)"
                    ),
                    mac,
                    self.alarm_name,
                    self._unique_id,
                )

        result = await self.controller.start()
        if result != self.controller.ConnectionResult.SUCCESS:
            raise ConfigEntryNotReady(
                self._get_exception_message(
                    result, f"{self.controller.host}:{self.controller.port}"
                )
            )

        return True

    async def stop(self):
        """Stop the underlying Envisalink alarm panel."""

        if self.controller:
            await self.controller.stop()

    def _get_exception_message(self, error, location) -> str:
        if error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION:
            msg = "Unable to authenticate with Envisalink"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED:
            msg = "Unable to connect to Envisalink"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_PANEL_TYPE:
            msg = "Unrecognized/undetermined panel type"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.INVALID_EVL_VERSION:
            msg = "Unrecognized/undetermined Envisalink version"
        elif error == EnvisalinkAlarmPanel.ConnectionResult.DISCOVERY_NOT_COMPLETE:
            msg = "Unable to complete discovery of Envisalink"
        else:
            msg = f"Unknown error: {error}"
        return f"{msg} at {location}"

    @property
    def available(self) -> bool:
        """Return if the Envisalink device is available or not."""
        return self.controller.is_online()

    @callback
    def async_login_fail_callback(self):
        """Handle when the evl rejects our login."""
        LOGGER.error("The Envisalink rejected your credentials")
        self._update_entity_states()

    @callback
    def async_login_timeout_callback(self):
        """Handle a login timeout."""
        LOGGER.error("Timed out trying to login to the Envisalink- retrying")
        self._update_entity_states()

    @callback
    def async_login_success_callback(self):
        """Handle a successful login."""
        LOGGER.info("Established a connection and logged into the Envisalink")
        self._update_entity_states()

    @callback
    def async_connection_status_callback(self, connected):
        """Handle when the evl rejects our login."""
        if not connected:
            # Trigger a state update for all the entities so they appear as unavailable
            self._update_entity_states()
        else:
            LOGGER.info("Connected to the envisalink device")

    @callback
    def async_zones_updated_callback(self, data: list):
        """Handle zone state updates."""
        LOGGER.debug(
            "Envisalink sent a '%s' zone update event. Updating zones: %r",
            self.alarm_name,
            data,
        )
        self._process_state_change(STATE_CHANGE_ZONE, data)

    @callback
    def async_keypad_updated_callback(self, data: list):
        """Handle non-alarm based info updates."""
        LOGGER.debug(
            "Envisalink sent '%s' new alarm info. Updating alarms: %r",
            self.alarm_name,
            data,
        )
        self._process_state_change(STATE_CHANGE_PARTITION, data)

    @callback
    def async_partition_updated_callback(self, data: list):
        """Handle partition changes thrown by evl (including alarms)."""
        LOGGER.debug(
            "The envisalink '%s' sent a partition update event: %r",
            self.alarm_name,
            data,
        )
        self._process_state_change(STATE_CHANGE_PARTITION, data)

    @callback
    def async_zone_bypass_update(self, data: list):
        """Handle zone bypass status updates."""
        LOGGER.debug(
            "Envisalink '%s' sent a zone bypass update event. Updating zones: %r",
            self.alarm_name,
            data,
        )
        self._process_state_change(STATE_CHANGE_ZONE_BYPASS, data)

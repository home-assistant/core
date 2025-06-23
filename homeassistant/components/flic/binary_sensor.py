"""Support to use flic buttons as a binary sensor."""

from __future__ import annotations

import logging
import threading

import pyflic
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3

CLICK_TYPE_SINGLE = "single"
CLICK_TYPE_DOUBLE = "double"
CLICK_TYPE_HOLD = "hold"
CLICK_TYPES = [CLICK_TYPE_SINGLE, CLICK_TYPE_DOUBLE, CLICK_TYPE_HOLD]

CONF_IGNORED_CLICK_TYPES = "ignored_click_types"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5551

EVENT_NAME = "flic_click"
EVENT_DATA_NAME = "button_name"
EVENT_DATA_ADDRESS = "button_address"
EVENT_DATA_TYPE = "click_type"
EVENT_DATA_QUEUED_TIME = "queued_time"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_IGNORED_CLICK_TYPES): vol.All(
            cv.ensure_list, [vol.In(CLICK_TYPES)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the flic platform."""

    # Initialize flic client responsible for
    # connecting to buttons and retrieving events
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    discovery = config.get(CONF_DISCOVERY)

    try:
        client = pyflic.FlicClient(host, port)
    except ConnectionRefusedError:
        _LOGGER.error("Failed to connect to flic server")
        return

    def new_button_callback(address):
        """Set up newly verified button as device in Home Assistant."""
        setup_button(hass, config, add_entities, client, address)

    client.on_new_verified_button = new_button_callback
    if discovery:
        start_scanning(config, add_entities, client)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: client.close())

    # Start the pyflic event handling thread
    threading.Thread(target=client.handle_events).start()

    def get_info_callback(items):
        """Add entities for already verified buttons."""
        addresses = items["bd_addr_of_verified_buttons"] or []
        for address in addresses:
            setup_button(hass, config, add_entities, client, address)

    # Get addresses of already verified buttons
    client.get_info(get_info_callback)


def start_scanning(config, add_entities, client):
    """Start a new flic client for scanning and connecting to new buttons."""
    scan_wizard = pyflic.ScanWizard()

    def scan_completed_callback(scan_wizard, result, address, name):
        """Restart scan wizard to constantly check for new buttons."""
        if result == pyflic.ScanWizardResult.WizardSuccess:
            _LOGGER.debug("Found new button %s", address)
        elif result != pyflic.ScanWizardResult.WizardFailedTimeout:
            _LOGGER.warning(
                "Failed to connect to button %s. Reason: %s", address, result
            )

        # Restart scan wizard
        start_scanning(config, add_entities, client)

    scan_wizard.on_completed = scan_completed_callback
    client.add_scan_wizard(scan_wizard)


def setup_button(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    client,
    address,
) -> None:
    """Set up a single button device."""
    timeout: int = config[CONF_TIMEOUT]
    ignored_click_types: list[str] | None = config.get(CONF_IGNORED_CLICK_TYPES)
    button = FlicButton(hass, client, address, timeout, ignored_click_types)
    _LOGGER.debug("Connected to button %s", address)

    add_entities([button])


class FlicButton(BinarySensorEntity):
    """Representation of a flic button."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        client: pyflic.FlicClient,
        address: str,
        timeout: int,
        ignored_click_types: list[str] | None,
    ) -> None:
        """Initialize the flic button."""

        self._attr_extra_state_attributes = {"address": address}
        self._attr_name = f"flic_{address.replace(':', '')}"
        self._attr_unique_id = format_mac(address)
        self._hass = hass
        self._address = address
        self._timeout = timeout
        self._attr_is_on = True
        self._ignored_click_types = ignored_click_types or []
        self._hass_click_types = {
            pyflic.ClickType.ButtonClick: CLICK_TYPE_SINGLE,
            pyflic.ClickType.ButtonSingleClick: CLICK_TYPE_SINGLE,
            pyflic.ClickType.ButtonDoubleClick: CLICK_TYPE_DOUBLE,
            pyflic.ClickType.ButtonHold: CLICK_TYPE_HOLD,
        }

        self._channel = self._create_channel()
        client.add_connection_channel(self._channel)

    def _create_channel(self) -> pyflic.ButtonConnectionChannel:
        """Create a new connection channel to the button."""
        channel = pyflic.ButtonConnectionChannel(self._address)
        channel.on_button_up_or_down = self._on_up_down

        # If all types of clicks should be ignored, skip registering callbacks
        if set(self._ignored_click_types) == set(CLICK_TYPES):
            return channel

        if CLICK_TYPE_DOUBLE in self._ignored_click_types:
            # Listen to all but double click type events
            channel.on_button_click_or_hold = self._on_click
        elif CLICK_TYPE_HOLD in self._ignored_click_types:
            # Listen to all but hold click type events
            channel.on_button_single_or_double_click = self._on_click
        else:
            # Listen to all click type events
            channel.on_button_single_or_double_click_or_hold = self._on_click

        return channel

    def _queued_event_check(self, click_type, time_diff):
        """Generate a log message and returns true if timeout exceeded."""
        time_string = f"{time_diff:d} {'second' if time_diff == 1 else 'seconds'}"

        if time_diff > self._timeout:
            _LOGGER.warning(
                "Queued %s dropped for %s. Time in queue was %s",
                click_type,
                self._address,
                time_string,
            )
            return True
        _LOGGER.debug(
            "Queued %s allowed for %s. Time in queue was %s",
            click_type,
            self._address,
            time_string,
        )
        return False

    def _on_up_down(self, channel, click_type, was_queued, time_diff):
        """Update device state, if event was not queued."""
        if was_queued and self._queued_event_check(click_type, time_diff):
            return

        self._attr_is_on = click_type != pyflic.ClickType.ButtonDown
        self.schedule_update_ha_state()

    def _on_click(self, channel, click_type, was_queued, time_diff):
        """Fire click event, if event was not queued."""
        # Return if click event was queued beyond allowed timeout
        if was_queued and self._queued_event_check(click_type, time_diff):
            return

        # Return if click event is in ignored click types
        hass_click_type = self._hass_click_types[click_type]
        if hass_click_type in self._ignored_click_types:
            return

        self._hass.bus.fire(
            EVENT_NAME,
            {
                EVENT_DATA_NAME: self.name,
                EVENT_DATA_ADDRESS: self._address,
                EVENT_DATA_QUEUED_TIME: time_diff,
                EVENT_DATA_TYPE: hass_click_type,
            },
        )

    def _connection_status_changed(self, channel, connection_status, disconnect_reason):
        """Remove device, if button disconnects."""
        if connection_status == pyflic.ConnectionStatus.Disconnected:
            _LOGGER.warning(
                "Button (%s) disconnected. Reason: %s", self._address, disconnect_reason
            )

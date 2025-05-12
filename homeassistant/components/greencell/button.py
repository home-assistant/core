import logging
import json
from typing import Callable

from homeassistant.components.mqtt import async_subscribe
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry

from .const import (
    EvseStateEnum, GreencellHaAccessLevelEnum as AccessLevel,
    MANUFACTURER, GREENCELL_HABU_DEN, GREENCELL_OTHER_DEVICE, GREENCELL_HABU_DEN_SERIAL_PREFIX
)

from .helper import GreencellAccess

_LOGGER = logging.getLogger(__name__)

class EvseStateData:
    """Simple internal EVSE state tracker (charging / idle)."""

    def __init__(self) -> None:
        self._state = EvseStateEnum.UNKNOWN
        self._listeners = []

    def update(self, new_state: str) -> None:
        """Update the EVSE state based on the received message."""
        if 'IDLE' == new_state:
            self._state = EvseStateEnum.IDLE
        elif 'CONNECTED' == new_state:
            self._state = EvseStateEnum.CONNECTED
        elif 'WAITING_FOR_CAR' == new_state:
            self._state = EvseStateEnum.WAITING_FOR_CAR
        elif 'CHARGING' == new_state:
            self._state = EvseStateEnum.CHARGING
        elif 'FINISHED' == new_state:
            self._state = EvseStateEnum.FINISHED
        elif 'ERROR_CAR' == new_state:
            self._state = EvseStateEnum.ERROR_CAR
        elif 'ERROR_EVSE' == new_state:
            self._state = EvseStateEnum.ERROR_EVSE
        else:
            self._state = EvseStateEnum.UNKNOWN

        self._notify_listeners()
        _LOGGER.debug(f'EVSE state updated to {self._state}')

    def is_charging(self) -> bool:
        """Check if the EVSE is currently charging and can be stopped."""
        return EvseStateEnum.CHARGING == self._state

    def can_be_stopped(self) -> bool:
        """Check if the EVSE is in a state where charging can be stopped."""
        return EvseStateEnum.WAITING_FOR_CAR == self._state

    def can_be_started(self) -> bool:
        """Check if the EVSE is in a state where charging can be started."""
        return EvseStateEnum.FINISHED == self._state or EvseStateEnum.CONNECTED == self._state

    def set_charging(self, value: bool) -> None:
        """Set the charging state of the EVSE."""
        self._charging = value

    def register_listener(self, listener: Callable[[], None]) -> None:
        """Register a listener to be notified of state changes."""
        self._listeners.append(listener)

    def _notify_listeners(self) -> None:
        """Notify all registered listeners of a state change."""
        for listener in self._listeners:
            listener()


class EVSEChargingButton(ButtonEntity):
    """Base class for EVSE charging buttons."""

    def __init__(
        self,
        serial_number: str,
        mqtt_topic: str,
        evse_state: EvseStateData,
        name: str,
        icon: str,
        action: str,
        access: GreencellAccess
    ) -> None:
        self._serial = serial_number
        self._mqtt_topic = mqtt_topic
        self._evse_state = evse_state
        self._attr_name = name
        self._icon = icon
        self._action = action
        self._access = access

    def _device_is_habu_den(self) -> bool:
        """Check if the device is a Habu Den based on its serial number."""
        return self._serial.startswith(GREENCELL_HABU_DEN_SERIAL_PREFIX)

    def _device_name(self) -> str:
        """Return the device name based on its type."""
        if self._device_is_habu_den():
            return GREENCELL_HABU_DEN
        else:
            return GREENCELL_OTHER_DEVICE

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the button (based on serial number of device)."""
        return f'{self._device_name()}_{self._serial}_{self._action.lower()}'

    @property
    def icon(self) -> str:
        """Return the icon for the button."""
        return self._icon

    @property
    def device_info(self) -> dict:
        """Return device information for the button."""
        return {
            'identifiers': {(self._serial,)},
            'name': f'{self._device_name()} {self._serial}',
            'manufacturer': MANUFACTURER,
            'model': self._device_name(),
        }

    async def async_press(self) -> None:
        """Handle button press."""
        payload = f'{{"name": "{self._action.upper()}"}}'
        await self.hass.services.async_call(
            'mqtt',
            'publish',
            {
                'topic': self._mqtt_topic,
                'payload': payload,
                'retain': False,
            },
            blocking=True,
        )
        self._update_evse_state()
        self.async_write_ha_state()

    def _update_evse_state(self) -> None:
        """To be implemented in subclasses if needed."""
        pass

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        self._evse_state.register_listener(self._schedule_update)
        self._access.register_listener(self._schedule_update)

    def _schedule_update(self):
        """Schedule state update from external EVSE state change."""
        if self.hass:
            self.async_write_ha_state()


class StartChargingButton(EVSEChargingButton):
    def __init__(self, serial_number: str, mqtt_topic: str, evse_state, access: GreencellAccess) -> None:
        super().__init__(
            serial_number,
            mqtt_topic,
            evse_state,
            name='Start Charging',
            icon='mdi:play-circle-outline',
            action='START',
            access=access,
        )

    @property
    def available(self) -> bool:
        """Return True if the button is available (when charging is not allowed by user)."""
        return self._evse_state.can_be_started() and self._access.can_execute()

    def _update_evse_state(self) -> None:
        """Update the EVSE state to indicate that charging has started."""
        self._evse_state.set_charging(True)


class StopChargingButton(EVSEChargingButton):
    def __init__(self, serial_number: str, mqtt_topic: str, evse_state, access: GreencellAccess) -> None:
        super().__init__(
            serial_number,
            mqtt_topic,
            evse_state,
            name='Stop Charging',
            icon='mdi:stop-circle-outline',
            action="STOP",
            access=access,
        )

    @property
    def available(self) -> bool:
        """Return True if the button is available (when device can charge / is charging)."""
        return (self._evse_state.is_charging() or self._evse_state.can_be_stopped()) and self._access.can_execute()

    def _update_evse_state(self) -> None:
        """Update the EVSE state to indicate that charging has stopped."""
        self._evse_state.set_charging(False)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Greencell EVSE buttons from YAML/discovery."""
    serial_number = discovery_info.get('serial_number') if discovery_info else config.get('serial_number')

    if not serial_number:
        _LOGGER.error('Serial number not provided in discovery info or config.')
        return

    await _setup_evse_buttons(hass, async_add_entities, serial_number)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Greencell EVSE buttons from config entry."""
    serial_number = discovery_info.get('serial_number') if discovery_info else entry.data.get('serial_number')

    if not serial_number:
        _LOGGER.error('Serial number not provided in discovery info or entry data.')
        return

    await _setup_evse_buttons(hass, async_add_entities, serial_number)


async def _setup_evse_buttons(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    serial_number: str,
) -> None:
    """Set up the Greencell EVSE buttons."""
    mqtt_cmd_topic = f'/greencell/evse/{serial_number}/cmd'
    mqtt_topic_status = f'/greencell/evse/{serial_number}/status'
    mqtt_ha_access_topic = f'/greencell/evse/{serial_number}/device_state'

    evse_state_object = EvseStateData()
    access = GreencellAccess(AccessLevel.EXECUTE)

    @callback
    def state_msg_received(msg) -> None:
        """Handle incoming MQTT messages for EVSE state. If LWT message is received, update the state to OFFLINE."""
        try:
            data = json.loads(msg.payload)
            if 'state' in data:
                state = data['state']
                if 'OFFLINE' in state:
                    access.update('OFFLINE')
                else:
                    evse_state_object.update(state)
        except json.JSONDecodeError as e:
            _LOGGER.error(f'Error decoding JSON message: {e}')
        except Exception as e:
            _LOGGER.error(f'Unexpected error: {e}')

    @callback
    def device_state_msg_received(msg) -> None:
        """Handle incoming MQTT messages for device state. If access level is different from EXECUTE, disable buttons."""
        try:
            data = json.loads(msg.payload)
            if 'level' in data:
                access.update(data['level'])
        except json.JSONDecodeError as e:
            _LOGGER.error(f'Failed to decode HA access message: {e}')
        except Exception as e:
            _LOGGER.error(f'Unexpected error: {e}')

    await async_subscribe(hass, mqtt_ha_access_topic, device_state_msg_received)
    await async_subscribe(hass, mqtt_topic_status, state_msg_received)

    buttons = [
        StartChargingButton(serial_number, mqtt_cmd_topic, evse_state_object, access),
        StopChargingButton(serial_number, mqtt_cmd_topic, evse_state_object, access),
    ]

    async_add_entities(buttons)

"""
Alexa Devices Sensors.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
import datetime
import logging
from typing import Callable, List, Optional, Text  # noqa pylint: disable=unused-import

from homeassistant.const import (
    DEVICE_CLASS_TIMESTAMP,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    __version__ as HA_VERSION,
)
from homeassistant.exceptions import ConfigEntryNotReady, NoEntitySpecifiedError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt
from packaging import version
import pytz

from . import (
    CONF_EMAIL,
    CONF_EXCLUDE_DEVICES,
    CONF_INCLUDE_DEVICES,
    DATA_ALEXAMEDIA,
    DOMAIN as ALEXA_DOMAIN,
    hide_email,
    hide_serial,
)
from .alexa_entity import parse_temperature_from_coordinator
from .const import (
    CONF_EXTENDED_ENTITY_DISCOVERY,
    RECURRING_PATTERN,
    RECURRING_PATTERN_ISO_SET,
)
from .helpers import add_devices, alarm_just_dismissed

_LOGGER = logging.getLogger(__name__)

LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo


async def async_setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the Alexa sensor platform."""
    devices: List[AlexaMediaNotificationSensor] = []
    SENSOR_TYPES = {
        "Alarm": AlarmSensor,
        "Timer": TimerSensor,
        "Reminder": ReminderSensor,
    }
    account = config[CONF_EMAIL] if config else discovery_info["config"][CONF_EMAIL]
    include_filter = config.get(CONF_INCLUDE_DEVICES, [])
    exclude_filter = config.get(CONF_EXCLUDE_DEVICES, [])
    account_dict = hass.data[DATA_ALEXAMEDIA]["accounts"][account]
    _LOGGER.debug("%s: Loading sensors", hide_email(account))
    if "sensor" not in account_dict["entities"]:
        (hass.data[DATA_ALEXAMEDIA]["accounts"][account]["entities"]["sensor"]) = {}
    for key, device in account_dict["devices"]["media_player"].items():
        if key not in account_dict["entities"]["media_player"]:
            _LOGGER.debug(
                "%s: Media player %s not loaded yet; delaying load",
                hide_email(account),
                hide_serial(key),
            )
            raise ConfigEntryNotReady
        if key not in (account_dict["entities"]["sensor"]):
            (account_dict["entities"]["sensor"][key]) = {}
            for (n_type, class_) in SENSOR_TYPES.items():
                n_type_dict = (
                    account_dict["notifications"][key][n_type]
                    if key in account_dict["notifications"]
                    and n_type in account_dict["notifications"][key]
                    else {}
                )
                if (
                    n_type in ("Alarm, Timer")
                    and "TIMERS_AND_ALARMS" in device["capabilities"]
                ):
                    alexa_client = class_(
                        account_dict["entities"]["media_player"][key],
                        n_type_dict,
                        account,
                    )
                elif n_type in ("Reminder") and "REMINDERS" in device["capabilities"]:
                    alexa_client = class_(
                        account_dict["entities"]["media_player"][key],
                        n_type_dict,
                        account,
                    )
                else:
                    continue
                _LOGGER.debug(
                    "%s: Found %s %s sensor (%s) with next: %s",
                    hide_email(account),
                    hide_serial(key),
                    n_type,
                    len(n_type_dict.keys()),
                    alexa_client.state,
                )
                devices.append(alexa_client)
                (account_dict["entities"]["sensor"][key][n_type]) = alexa_client
        else:
            for alexa_client in account_dict["entities"]["sensor"][key].values():
                _LOGGER.debug(
                    "%s: Skipping already added device: %s",
                    hide_email(account),
                    alexa_client,
                )

    temperature_sensors = []
    temperature_entities = account_dict.get("devices", {}).get("temperature", [])
    if temperature_entities and account_dict["options"].get(
        CONF_EXTENDED_ENTITY_DISCOVERY
    ):
        temperature_sensors = await create_temperature_sensors(
            account_dict, temperature_entities
        )

    return await add_devices(
        hide_email(account),
        devices + temperature_sensors,
        add_devices_callback,
        include_filter,
        exclude_filter,
    )


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Alexa sensor platform by config_entry."""
    return await async_setup_platform(
        hass, config_entry.data, async_add_devices, discovery_info=None
    )


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    account = entry.data[CONF_EMAIL]
    account_dict = hass.data[DATA_ALEXAMEDIA]["accounts"][account]
    _LOGGER.debug("Attempting to unload sensors")
    for key, sensors in account_dict["entities"]["sensor"].items():
        for device in sensors[key].values():
            _LOGGER.debug("Removing %s", device)
            await device.async_remove()
    return True


async def create_temperature_sensors(account_dict, temperature_entities):
    devices = []
    coordinator = account_dict["coordinator"]
    for temp in temperature_entities:
        _LOGGER.debug(
            "Creating entity %s for a temperature sensor with name %s",
            temp["id"],
            temp["name"],
        )
        serial = temp["device_serial"]
        device_info = lookup_device_info(account_dict, serial)
        sensor = TemperatureSensor(coordinator, temp["id"], temp["name"], device_info)
        account_dict["entities"]["sensor"].setdefault(serial, {})
        account_dict["entities"]["sensor"][serial]["Temperature"] = sensor
        devices.append(sensor)
    return devices


def lookup_device_info(account_dict, device_serial):
    """Get the device to use for a given Echo based on a given device serial id.

    This may return nothing as there is no guarantee that a given temperature sensor is actually attached to an Echo.
    """
    for key, mp in account_dict["entities"]["media_player"].items():
        if key == device_serial and mp.device_info and "identifiers" in mp.device_info:
            for ident in mp.device_info["identifiers"]:
                return ident
    return None


class TemperatureSensor(CoordinatorEntity):
    """A temperature sensor reported by an Echo."""

    def __init__(self, coordinator, entity_id, name, media_player_device_id):
        super().__init__(coordinator)
        self.alexa_entity_id = entity_id
        self._name = name
        self._media_player_device_id = media_player_device_id

    @property
    def name(self):
        return self._name + " Temperature"

    @property
    def device_info(self):
        """Return the device_info of the device."""
        if self._media_player_device_id:
            return {
                "identifiers": {self._media_player_device_id},
                "via_device": self._media_player_device_id,
            }
        return None

    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS

    @property
    def state(self):
        return parse_temperature_from_coordinator(
            self.coordinator, self.alexa_entity_id
        )

    @property
    def unique_id(self):
        # This includes "_temperature" because the Alexa entityId is for a physical device
        # A single physical device could have multiple HA entities
        return self.alexa_entity_id + "_temperature"


class AlexaMediaNotificationSensor(Entity):
    """Representation of Alexa Media sensors."""

    def __init__(
        self,
        client,
        n_dict,
        sensor_property: Text,
        account,
        name="Next Notification",
        icon=None,
    ):
        """Initialize the Alexa sensor device."""
        # Class info
        self._client = client
        self._n_dict = n_dict
        self._sensor_property = sensor_property
        self._account = account
        self._dev_id = client.unique_id
        self._name = name
        self._unit = None
        self._device_class = DEVICE_CLASS_TIMESTAMP
        self._icon = icon
        self._all = []
        self._active = []
        self._next = None
        self._prior_value = None
        self._timestamp: Optional[datetime.datetime] = None
        self._tracker: Optional[Callable] = None
        self._state: Optional[datetime.datetime] = None
        self._dismissed: Optional[datetime.datetime] = None
        self._status: Optional[Text] = None
        self._amz_id: Optional[Text] = None
        self._version: Optional[Text] = None

    def _process_raw_notifications(self):
        self._all = (
            list(map(self._fix_alarm_date_time, self._n_dict.items()))
            if self._n_dict
            else []
        )
        self._all = list(map(self._update_recurring_alarm, self._all))
        self._all = sorted(self._all, key=lambda x: x[1][self._sensor_property])
        self._prior_value = self._next if self._active else None
        self._active = (
            list(filter(lambda x: x[1]["status"] in ("ON", "SNOOZED"), self._all))
            if self._all
            else []
        )
        self._next = self._active[0][1] if self._active else None
        alarm = next(
            (alarm[1] for alarm in self._all if alarm[1].get("id") == self._amz_id),
            None,
        )
        if alarm_just_dismissed(alarm, self._status, self._version):
            self._dismissed = dt.now().isoformat()
        self._state = self._process_state(self._next)
        self._status = self._next.get("status", "OFF") if self._next else "OFF"
        self._version = self._next.get("version", "0") if self._next else None
        self._amz_id = self._next.get("id") if self._next else None

        if self._state == STATE_UNAVAILABLE or self._next != self._prior_value:
            # cancel any event triggers
            if self._tracker:
                _LOGGER.debug(
                    "%s: Cancelling old event",
                    self,
                )
                self._tracker()
            if self._state != STATE_UNAVAILABLE and self._status != "SNOOZED":
                _LOGGER.debug(
                    "%s: Scheduling event in %s",
                    self,
                    dt.as_utc(dt.parse_datetime(self._state)) - dt.utcnow(),
                )
                self._tracker = async_track_point_in_utc_time(
                    self.hass,
                    self._trigger_event,
                    dt.as_utc(dt.parse_datetime(self._state)),
                )

    def _trigger_event(self, time_date) -> None:
        _LOGGER.debug(
            "%s:Firing %s at %s",
            self,
            "alexa_media_notification_event",
            dt.as_local(time_date),
        )
        self.hass.bus.async_fire(
            "alexa_media_notification_event",
            event_data={
                "email": hide_email(self._account),
                "device": {"name": self.name, "entity_id": self.entity_id},
                "event": self._active[0],
            },
        )

    def _fix_alarm_date_time(self, value):
        if (
            self._sensor_property != "date_time"
            or not value
            or isinstance(value[1][self._sensor_property], datetime.datetime)
        ):
            return value
        naive_time = dt.parse_datetime(value[1][self._sensor_property])
        timezone = pytz.timezone(self._client._timezone)
        if timezone and naive_time:
            value[1][self._sensor_property] = timezone.localize(naive_time)
        elif not naive_time:
            # this is typically an older alarm
            value[1][self._sensor_property] = datetime.datetime.fromtimestamp(
                value[1]["alarmTime"] / 1000, tz=LOCAL_TIMEZONE
            )
            _LOGGER.warning(
                "There is an old format alarm on %s set for %s. "
                " This alarm should be removed in the Alexa app and recreated. ",
                self._client.name,
                dt.as_local(value[1][self._sensor_property]),
            )
        else:
            _LOGGER.warning(
                "%s is returning erroneous data. "
                "Returned times may be wrong. "
                "Please confirm the timezone in the Alexa app is correct. "
                "Debugging info: \nRaw: %s \nNaive Time: %s "
                "\nTimezone: %s",
                self._client.name,
                value[1],
                naive_time,
                self._client._timezone,
            )
        return value

    def _update_recurring_alarm(self, value):
        _LOGGER.debug("Sensor value %s", value)
        alarm = value[1][self._sensor_property]
        reminder = None
        if isinstance(value[1][self._sensor_property], (int, float)):
            reminder = True
            alarm = dt.as_local(
                self._round_time(
                    datetime.datetime.fromtimestamp(alarm / 1000, tz=LOCAL_TIMEZONE)
                )
            )
        alarm_on = value[1]["status"] == "ON"
        recurring_pattern = value[1].get("recurringPattern")
        while (
            alarm_on
            and recurring_pattern
            and RECURRING_PATTERN_ISO_SET.get(recurring_pattern)
            and alarm.isoweekday not in RECURRING_PATTERN_ISO_SET[recurring_pattern]
            and alarm < dt.now()
        ):
            alarm += datetime.timedelta(days=1)
        if reminder:
            alarm = dt.as_timestamp(alarm) * 1000
        if alarm != value[1][self._sensor_property]:
            _LOGGER.debug(
                "%s with recurrence %s set to %s",
                value[1]["type"],
                RECURRING_PATTERN[recurring_pattern],
                alarm,
            )
            value[1][self._sensor_property] = alarm
        return value

    @staticmethod
    def _round_time(value: datetime.datetime) -> datetime.datetime:
        precision = datetime.timedelta(seconds=1).total_seconds()
        seconds = (value - value.min.replace(tzinfo=value.tzinfo)).seconds
        rounding = (seconds + precision / 2) // precision * precision
        return value + datetime.timedelta(0, rounding - seconds, -value.microsecond)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        try:
            if not self.enabled:
                return
        except AttributeError:
            pass
        self._process_raw_notifications()
        # Register event handler on bus
        self._listener = async_dispatcher_connect(
            self.hass,
            f"{ALEXA_DOMAIN}_{hide_email(self._account)}"[0:32],
            self._handle_event,
        )
        await self.async_update()

    async def async_will_remove_from_hass(self):
        """Prepare to remove entity."""
        # Register event handler on bus
        self._listener()
        if self._tracker:
            self._tracker()

    def _handle_event(self, event):
        """Handle events.

        This will update PUSH_NOTIFICATION_CHANGE events to see if the sensor
        should be updated.
        """
        try:
            if not self.enabled:
                return
        except AttributeError:
            pass
        if "notification_update" in event:
            if (
                event["notification_update"]["dopplerId"]["deviceSerialNumber"]
                == self._client.device_serial_number
            ):
                _LOGGER.debug("Updating sensor %s", self)
                self.async_schedule_update_ha_state(True)

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._client.available

    @property
    def assumed_state(self):
        """Return whether the state is an assumed_state."""
        return self._client.assumed_state

    @property
    def hidden(self):
        """Return whether the sensor should be hidden."""
        return self.state == STATE_UNAVAILABLE

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"{self._client.unique_id}_{self._name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client.name} {self._name}"

    @property
    def should_poll(self):
        """Return the polling state."""
        return not (
            self.hass.data[DATA_ALEXAMEDIA]["accounts"][self._account]["websocket"]
        )

    @property
    def state(self) -> datetime.datetime:
        """Return the state of the sensor."""
        return self._state

    def _process_state(self, value):
        return (
            dt.as_local(value[self._sensor_property]).isoformat()
            if value
            else STATE_UNAVAILABLE
        )

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit

    @property
    def device_class(self):
        """Return the device_class of the device."""
        return self._device_class

    async def async_update(self):
        """Update state."""
        try:
            if not self.enabled:
                return
        except AttributeError:
            pass
        account_dict = self.hass.data[DATA_ALEXAMEDIA]["accounts"][self._account]
        self._timestamp = account_dict["notifications"]["process_timestamp"]
        try:
            self._n_dict = account_dict["notifications"][self._dev_id][self._type]
        except KeyError:
            self._n_dict = None
        self._process_raw_notifications()
        try:
            self.async_write_ha_state()
        except NoEntitySpecifiedError:
            pass  # we ignore this due to a harmless startup race condition

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(ALEXA_DOMAIN, self._dev_id)},
            "via_device": (ALEXA_DOMAIN, self._dev_id),
        }

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def recurrence(self):
        """Return the recurrence pattern of the sensor."""
        return (
            RECURRING_PATTERN[self._next.get("recurringPattern")]
            if self._next
            else None
        )

    @property
    def device_state_attributes(self):
        """Return additional attributes."""
        import json

        attr = {
            "recurrence": self.recurrence,
            "process_timestamp": dt.as_local(self._timestamp).isoformat(),
            "prior_value": self._process_state(self._prior_value),
            "total_active": len(self._active),
            "total_all": len(self._all),
            "sorted_active": json.dumps(self._active, default=str),
            "sorted_all": json.dumps(self._all, default=str),
            "status": self._status,
            "dismissed": self._dismissed,
        }
        return attr


class AlarmSensor(AlexaMediaNotificationSensor):
    """Representation of a Alexa Alarm sensor."""

    def __init__(self, client, n_json, account):
        """Initialize the Alexa sensor."""
        # Class info
        self._type = "Alarm"
        super().__init__(
            client, n_json, "date_time", account, f"next {self._type}", "mdi:alarm"
        )


class TimerSensor(AlexaMediaNotificationSensor):
    """Representation of a Alexa Timer sensor."""

    def __init__(self, client, n_json, account):
        """Initialize the Alexa sensor."""
        # Class info
        self._type = "Timer"
        super().__init__(
            client,
            n_json,
            "remainingTime",
            account,
            f"next {self._type}",
            "mdi:timer-outline"
            if (version.parse(HA_VERSION) >= version.parse("0.113.0"))
            else "mdi:timer",
        )

    def _process_state(self, value):
        return (
            dt.as_local(
                super()._round_time(
                    self._timestamp
                    + datetime.timedelta(milliseconds=value[self._sensor_property])
                )
            ).isoformat()
            if value and self._timestamp
            else STATE_UNAVAILABLE
        )

    @property
    def paused(self) -> Optional[bool]:
        """Return the paused state of the sensor."""
        return self._next["status"] == "PAUSED" if self._next else None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        off_icon = (
            "mdi:timer-off-outline"
            if (version.parse(HA_VERSION) >= version.parse("0.113.0"))
            else "mdi:timer-off"
        )
        return self._icon if not self.paused else off_icon


class ReminderSensor(AlexaMediaNotificationSensor):
    """Representation of a Alexa Reminder sensor."""

    def __init__(self, client, n_json, account):
        """Initialize the Alexa sensor."""
        # Class info
        self._type = "Reminder"
        super().__init__(
            client, n_json, "alarmTime", account, f"next {self._type}", "mdi:reminder"
        )

    def _process_state(self, value):
        return (
            dt.as_local(
                super()._round_time(
                    datetime.datetime.fromtimestamp(
                        value[self._sensor_property] / 1000, tz=LOCAL_TIMEZONE
                    )
                )
            ).isoformat()
            if value
            else STATE_UNAVAILABLE
        )

    @property
    def reminder(self):
        """Return the reminder of the sensor."""
        return self._next["reminderLabel"] if self._next else None

    @property
    def device_state_attributes(self):
        """Return the scene state attributes."""
        attr = super().device_state_attributes
        attr.update({"reminder": self.reminder})
        return attr

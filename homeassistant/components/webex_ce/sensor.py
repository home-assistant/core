"""Sensor platform for Webex CE devices."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.util.dt as dt_util

from . import WebexCEConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming device
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebexCEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webex CE sensor entities."""
    client = entry.runtime_data

    # Get device info for device registry
    device_info = await client.get_device_info()

    # Create device info dict
    device_info_dict = DeviceInfo(
        identifiers={(DOMAIN, device_info["serial"])},
        name=entry.title,
        manufacturer="Cisco",
        model=device_info["product"],
        sw_version=device_info["software_version"],
    )

    # Add all sensors - ordered by importance/usage
    async_add_entities(
        [
            # Call and meeting status
            WebexCECallStatusSensor(client, device_info_dict),
            WebexCECurrentMeetingSensor(client, device_info_dict),
            WebexCENextMeetingSensor(client, device_info_dict),
            # Recording and streaming
            WebexCERecordingSensor(client, device_info_dict),
            WebexCEStreamingSensor(client, device_info_dict),
            # Room analytics
            WebexCEPeoplePresenceSensor(client, device_info_dict),
            WebexCESoundLevelSensor(client, device_info_dict),
            WebexCEAmbientNoiseSensor(client, device_info_dict),
            WebexCETemperatureSensor(client, device_info_dict),
            WebexCEHumiditySensor(client, device_info_dict),
            # Network and system
            WebexCENetworkStatusSensor(client, device_info_dict),
            WebexCESystemUptimeSensor(client, device_info_dict),
        ]
    )


class WebexCECallStatusSensor(SensorEntity):
    """Sensor for active call status and details.

    Monitors Status/Call and Status/Conference xAPI paths to provide
    current call state (idle/connected/ringing etc), call direction,
    duration, and remote party information.
    """

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        # Extract serial from device info identifiers
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_call_status"
        self._attr_native_value = "idle"
        self._attr_extra_state_attributes = {}
        self._call_data: dict[str, Any] | None = None
        self._conference_data: dict[str, Any] | None = None
        self._call_start_time: datetime | None = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    @property
    def icon(self) -> str:
        """Return the icon based on call state."""
        if self._attr_native_value == "connected":
            return "mdi:phone-in-talk"
        if self._attr_native_value == "ringing":
            return "mdi:phone-ring"
        if self._attr_native_value == "on_hold":
            return "mdi:phone-paused"
        if self._attr_native_value in ("connecting", "disconnecting"):
            return "mdi:phone-clock"
        return "mdi:phone-off"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()

        _LOGGER.info(
            "Setting up call status sensor subscriptions for %s", self.unique_id
        )

        try:
            # Subscribe to call status updates
            await self._client.subscribe_feedback(
                f"{self.unique_id}_call",
                ["Status", "Call"],
                self._handle_call_feedback,
            )
            _LOGGER.info("Subscribed to Status/Call feedback")

            # Subscribe to conference status updates
            await self._client.subscribe_feedback(
                f"{self.unique_id}_conference",
                ["Status", "Conference"],
                self._handle_conference_feedback,
            )
            _LOGGER.info("Subscribed to Status/Conference feedback")
        except Exception:
            _LOGGER.exception("Error subscribing to feedback")

    @callback
    def _handle_call_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle call feedback from the device."""
        _LOGGER.info("Received call feedback for %s: %s", self.unique_id, params)

        try:
            call_data = params.get("Status", {}).get("Call")
            _LOGGER.info("Call data type: %s, value: %s", type(call_data), call_data)

            # Call can be an array or None
            if isinstance(call_data, list):
                # Use first call if multiple
                self._call_data = call_data[0] if call_data else None
            elif isinstance(call_data, dict):
                # Single call as dict
                self._call_data = call_data
            else:
                # No active calls
                self._call_data = None

            _LOGGER.info("Processed call_data: %s", self._call_data)
            self._update_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Unexpected call feedback format: %s, error: %s", params, err
            )

    @callback
    def _handle_conference_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle conference feedback from the device."""
        _LOGGER.info("Received conference feedback for %s: %s", self.unique_id, params)

        try:
            self._conference_data = params.get("Status", {}).get("Conference")
            self._update_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.warning(
                "Unexpected conference feedback format: %s, error: %s", params, err
            )

    def _extract_call_attributes(self) -> dict[str, Any]:
        """Extract attributes from call data."""
        if not self._call_data or not isinstance(self._call_data, dict):
            return {}

        attributes: dict[str, Any] = {}
        for key in (
            "DisplayName",
            "RemoteNumber",
            "CallbackNumber",
            "Protocol",
            "CallType",
            "CallId",
        ):
            if key in self._call_data:
                attr_key = key.replace("Number", "_number").lower()
                if "_" not in attr_key and key not in (
                    "Protocol",
                    "CallType",
                    "CallId",
                ):
                    attr_key = key[0].lower() + "".join(
                        f"_{c.lower()}" if c.isupper() else c for c in key[1:]
                    )
                attributes[attr_key if attr_key != "calltypeid" else "call_type"] = (
                    self._call_data[key].lower()
                    if key == "Direction"
                    else self._call_data[key]
                )

        if "Direction" in self._call_data:
            attributes["direction"] = self._call_data["Direction"].lower()

        return attributes

    def _extract_conference_attributes(self) -> dict[str, Any]:
        """Extract attributes from conference data."""
        attributes: dict[str, Any] = {}
        if not self._conference_data or not isinstance(self._conference_data, dict):
            return attributes

        # Check presentation mode
        pres_data = self._conference_data.get("Presentation", {})
        if isinstance(pres_data, dict) and "Mode" in pres_data:
            attributes["presentation_mode"] = pres_data["Mode"]

        # Get meeting info
        meeting_data = self._conference_data.get("ActiveMeeting", {})
        if isinstance(meeting_data, dict):
            if "Name" in meeting_data:
                attributes["meeting_name"] = meeting_data["Name"]
            if "Id" in meeting_data:
                attributes["meeting_id"] = meeting_data["Id"]

        # Get participant count
        participants = self._conference_data.get("Participants", {})
        if isinstance(participants, dict) and "Count" in participants:
            attributes["participants_count"] = participants["Count"]

        return attributes

    @callback
    def _update_state(self) -> None:
        """Update the sensor state and attributes based on call and conference data."""
        attributes = {}
        _LOGGER.info("Updating state, call_data: %s", self._call_data)

        if self._call_data:
            # Extract call status
            status = self._call_data.get("Status", "").lower()
            _LOGGER.info("Call status (lowercased): %s", status)

            # Map status to our states
            if status in ("connected", "connected"):
                self._attr_native_value = "connected"
            elif status in ("ringing", "alerting"):
                self._attr_native_value = "ringing"
            elif status in ("connecting", "dialing"):
                self._attr_native_value = "connecting"
            elif status in ("disconnecting", "ondisconnect"):
                self._attr_native_value = "disconnecting"
            elif status == "onhold":
                self._attr_native_value = "on_hold"
            else:
                self._attr_native_value = status or "idle"

            _LOGGER.info("Set native_value to: %s", self._attr_native_value)

            # Extract call attributes
            attributes.update(self._extract_call_attributes())

            # Calculate duration if we have start time
            answer_state = self._call_data.get("AnswerState")
            if answer_state == "Answered" and not self._call_start_time:
                self._call_start_time = dt_util.utcnow()
            elif answer_state and answer_state != "Answered":
                self._call_start_time = None

            if self._call_start_time and self._attr_native_value == "connected":
                duration = dt_util.utcnow() - self._call_start_time
                attributes["duration"] = str(duration).split(".", maxsplit=1)[0]
                attributes["duration_seconds"] = int(duration.total_seconds())
        else:
            # No active call
            self._attr_native_value = "idle"
            self._call_start_time = None

        # Add conference information
        attributes.update(self._extract_conference_attributes())

        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class WebexCEAmbientNoiseSensor(SensorEntity):
    """Representation of ambient noise level sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "ambient_noise"
    _attr_native_unit_of_measurement = "dBA"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:volume-high"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_ambient_noise"
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "RoomAnalytics", "AmbientNoise"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            noise_data = (
                params.get("Status", {})
                .get("RoomAnalytics", {})
                .get("AmbientNoise", {})
            )
            level_a = noise_data.get("Level", {}).get("A")
            if level_a is not None:
                self._attr_native_value = int(level_a)
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Unexpected ambient noise feedback: %s, error: %s", params, err
            )


class WebexCETemperatureSensor(SensorEntity):
    """Representation of ambient temperature sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "ambient_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_ambient_temperature"
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "RoomAnalytics", "AmbientTemperature"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            temp = (
                params.get("Status", {})
                .get("RoomAnalytics", {})
                .get("AmbientTemperature")
            )
            if temp is not None:
                self._attr_native_value = float(temp)
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Unexpected temperature feedback: %s, error: %s", params, err
            )


class WebexCEPeoplePresenceSensor(SensorEntity):
    """Representation of room occupancy sensor with all presence/availability details."""

    _attr_has_entity_name = True
    _attr_translation_key = "room_occupancy"
    _attr_icon = "mdi:account-multiple"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_room_occupancy"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        # Subscribe to presence, count, availability, and proximity
        await self._client.subscribe_feedback(
            f"{self.unique_id}_presence",
            ["Status", "RoomAnalytics", "PeoplePresence"],
            self._handle_presence_feedback,
        )
        await self._client.subscribe_feedback(
            f"{self.unique_id}_count",
            ["Status", "RoomAnalytics", "PeopleCount"],
            self._handle_count_feedback,
        )
        await self._client.subscribe_feedback(
            f"{self.unique_id}_availability",
            ["Status", "Bookings", "Availability", "Status"],
            self._handle_availability_feedback,
        )
        await self._client.subscribe_feedback(
            f"{self.unique_id}_proximity",
            ["Status", "RoomAnalytics", "Engagement", "CloseProximity"],
            self._handle_proximity_feedback,
        )

    @callback
    def _handle_presence_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle presence feedback from the device."""
        try:
            presence = (
                params.get("Status", {}).get("RoomAnalytics", {}).get("PeoplePresence")
            )
            if presence is not None:
                self._attr_native_value = presence.capitalize()
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug(
                "Unexpected people presence feedback: %s, error: %s", params, err
            )

    @callback
    def _handle_count_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle count feedback from the device."""
        try:
            people_data = (
                params.get("Status", {}).get("RoomAnalytics", {}).get("PeopleCount", {})
            )
            current = people_data.get("Current")
            capacity = people_data.get("Capacity")

            if current is not None:
                self._attr_extra_state_attributes["people_count"] = int(current)
            if capacity is not None:
                self._attr_extra_state_attributes["capacity"] = int(capacity)

            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Unexpected people count feedback: %s, error: %s", params, err
            )

    @callback
    def _handle_availability_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle room availability feedback from the device."""
        try:
            status = (
                params.get("Status", {})
                .get("Bookings", {})
                .get("Availability", {})
                .get("Status", "Free")
            )
            self._attr_extra_state_attributes["availability"] = status.capitalize()
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug(
                "Unexpected availability feedback: %s, error: %s", params, err
            )

    @callback
    def _handle_proximity_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle close proximity feedback from the device."""
        try:
            proximity = (
                params.get("Status", {})
                .get("RoomAnalytics", {})
                .get("Engagement", {})
                .get("CloseProximity", "False")
            )
            self._attr_extra_state_attributes["close_proximity"] = proximity in (
                "True",
                True,
                "true",
            )
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug("Unexpected proximity feedback: %s, error: %s", params, err)


class WebexCEHumiditySensor(SensorEntity):
    """Representation of relative humidity sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "relative_humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_relative_humidity"
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "RoomAnalytics", "RelativeHumidity"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            humidity = (
                params.get("Status", {})
                .get("RoomAnalytics", {})
                .get("RelativeHumidity")
            )
            if humidity is not None:
                self._attr_native_value = int(humidity)
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Unexpected humidity feedback: %s, error: %s", params, err)


class WebexCESoundLevelSensor(SensorEntity):
    """Representation of sound level sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "sound_level"
    _attr_native_unit_of_measurement = "dBA"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:waveform"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_sound_level"
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "RoomAnalytics", "Sound"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            sound_data = (
                params.get("Status", {}).get("RoomAnalytics", {}).get("Sound", {})
            )
            level_a = sound_data.get("Level", {}).get("A")
            if level_a is not None:
                self._attr_native_value = int(level_a)
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Unexpected sound level feedback: %s, error: %s", params, err
            )


class WebexCECurrentMeetingSensor(SensorEntity):
    """Representation of current meeting sensor with details in attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_meeting"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_current_meeting"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Bookings"],
            self._handle_feedback,
        )
        await self._update_bookings()

    async def _update_bookings(self) -> None:
        """Query bookings and update current meeting."""
        try:
            result = await self._client.xcommand(["Bookings", "List"])
            bookings = result.get("Booking", [])
            if not isinstance(bookings, list):
                bookings = [bookings] if bookings else []

            now = datetime.now(UTC)

            for booking in bookings:
                time_data = booking.get("Time", {})
                start = time_data.get("StartTime")
                end = time_data.get("EndTime")
                if start and end:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    if start_dt <= now < end_dt:
                        # Found current meeting - set title as state
                        self._attr_native_value = booking.get("Title")

                        # Add all details as attributes
                        organizer = booking.get("Organizer", {})
                        self._attr_extra_state_attributes = {
                            "organizer_name": organizer.get("FirstName", ""),
                            "organizer_email": organizer.get("Email", ""),
                            "start_time": start_dt.isoformat(),
                            "end_time": end_dt.isoformat(),
                            "meeting_id": booking.get("Id", ""),
                            "meeting_platform": booking.get("MeetingPlatform", ""),
                            "privacy": booking.get("Privacy", ""),
                        }
                        self.async_write_ha_state()
                        return

            # No current meeting
            self._attr_native_value = "No meeting"
            self._attr_extra_state_attributes = {}
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001 - Broad exception OK for background task
            _LOGGER.debug("Could not update current meeting bookings: %s", err)

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle booking status changes."""
        self.hass.async_create_task(self._update_bookings())


class WebexCENextMeetingSensor(SensorEntity):
    """Representation of next meeting sensor with details in attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_meeting"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_next_meeting"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Bookings"],
            self._handle_feedback,
        )
        await self._update_bookings()

    async def _update_bookings(self) -> None:
        """Query bookings and find next meeting."""
        try:
            result = await self._client.xcommand(["Bookings", "List"])
            bookings = result.get("Booking", [])
            if not isinstance(bookings, list):
                bookings = [bookings] if bookings else []

            now = datetime.now(UTC)

            # Find next meeting (starts after now)
            upcoming = []
            for booking in bookings:
                time_data = booking.get("Time", {})
                start = time_data.get("StartTime")
                end = time_data.get("EndTime")
                if start:
                    start_dt = datetime.fromisoformat(start)
                    if start_dt > now:
                        end_dt = datetime.fromisoformat(end) if end else None
                        upcoming.append((start_dt, end_dt, booking))

            if upcoming:
                # Sort by start time and get earliest
                upcoming.sort(key=lambda x: x[0])
                next_start, next_end, next_booking = upcoming[0]

                # Set title as state
                self._attr_native_value = next_booking.get("Title")

                # Add all details as attributes
                organizer = next_booking.get("Organizer", {})
                self._attr_extra_state_attributes = {
                    "organizer_name": organizer.get("FirstName", ""),
                    "organizer_email": organizer.get("Email", ""),
                    "start_time": next_start.isoformat(),
                    "end_time": next_end.isoformat() if next_end else None,
                    "meeting_id": next_booking.get("Id", ""),
                    "meeting_platform": next_booking.get("MeetingPlatform", ""),
                    "privacy": next_booking.get("Privacy", ""),
                }
            else:
                self._attr_native_value = None
                self._attr_extra_state_attributes = {}

            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001 - Broad exception OK for background task
            _LOGGER.debug("Could not update next meeting bookings: %s", err)

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle booking status changes."""
        self.hass.async_create_task(self._update_bookings())


class WebexCESystemUptimeSensor(SensorEntity):
    """Representation of system uptime sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "system_uptime"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_system_uptime"
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "SystemUnit", "Uptime"],
            self._handle_feedback,
        )

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            uptime = params.get("Status", {}).get("SystemUnit", {}).get("Uptime")
            if uptime is not None:
                self._attr_native_value = int(uptime)
                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning("Unexpected uptime feedback: %s - %s", params, err)


class WebexCENetworkStatusSensor(SensorEntity):
    """Representation of network status sensor with detailed attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "network_status"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_network_status"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        await self._client.subscribe_feedback(
            self.unique_id,
            ["Status", "Network"],
            self._handle_feedback,
        )
        # Query initial state
        try:
            status = await self._client.xget(["Status", "Network"])
            # unique_id is set in __init__, assert for mypy
            assert self.unique_id is not None
            self._handle_feedback({"Status": {"Network": status}}, self.unique_id)
        except Exception as err:  # noqa: BLE001 - Broad exception OK for background task
            _LOGGER.debug("Could not query initial network state: %s", err)

    @callback
    def _handle_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle feedback from the device."""
        try:
            network_list = params.get("Status", {}).get("Network", [])
            if isinstance(network_list, list) and network_list:
                network_data = network_list[0]

                # Main state: connected/disconnected based on IP presence
                ipv4_address = network_data.get("IPv4", {}).get("Address")
                self._attr_native_value = (
                    "connected" if ipv4_address else "disconnected"
                )

                # Attributes
                self._attr_extra_state_attributes = {}

                # IPv4
                if ipv4_address:
                    self._attr_extra_state_attributes["ipv4_address"] = ipv4_address
                    gateway = network_data.get("IPv4", {}).get("Gateway")
                    if gateway:
                        self._attr_extra_state_attributes["gateway"] = gateway

                # IPv6
                ipv6_data = network_data.get("IPv6", {})
                ipv6_address = ipv6_data.get("Address") or ipv6_data.get(
                    "LinkLocalAddress"
                )
                if ipv6_address:
                    self._attr_extra_state_attributes["ipv6_address"] = ipv6_address

                # MAC Address
                mac = network_data.get("Ethernet", {}).get("MacAddress")
                if mac:
                    self._attr_extra_state_attributes["mac_address"] = mac

                # Speed
                speed_str = network_data.get("Ethernet", {}).get("Speed")
                if speed_str:
                    match = re.match(r"(\d+)", str(speed_str))
                    if match:
                        self._attr_extra_state_attributes["speed_mbps"] = int(
                            match.group(1)
                        )

                # VLAN
                vlan_data = network_data.get("VLAN", {}).get("Voice", {})
                vlan_id = vlan_data.get("VlanId")
                if vlan_id and vlan_id != "Off":
                    self._attr_extra_state_attributes["vlan_id"] = int(vlan_id)

                self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, IndexError, ValueError) as err:
            _LOGGER.debug("Could not parse network status: %s", err)


class WebexCERecordingSensor(SensorEntity):
    """Representation of recording sensor with status and duration."""

    _attr_has_entity_name = True
    _attr_translation_key = "recording"
    _attr_icon = "mdi:record-rec"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_recording"
        self._attr_native_value = "No"
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        # Subscribe to both status and duration
        await self._client.subscribe_feedback(
            f"{self.unique_id}_status",
            ["Status", "Recording", "Status"],
            self._handle_status_feedback,
        )
        await self._client.subscribe_feedback(
            f"{self.unique_id}_duration",
            ["Status", "Recording", "Duration"],
            self._handle_duration_feedback,
        )

    @callback
    def _handle_status_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle status feedback from the device."""
        try:
            status = params.get("Status", {}).get("Recording", {}).get("Status", "Idle")
            # Set state to Yes/No based on recording status
            self._attr_native_value = (
                "Yes" if status in ("Recording", "Active") else "No"
            )
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug(
                "Unexpected recording status feedback: %s, error: %s", params, err
            )

    @callback
    def _handle_duration_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle duration feedback from the device."""
        try:
            duration = params.get("Status", {}).get("Recording", {}).get("Duration")
            if duration is not None:
                self._attr_extra_state_attributes["duration"] = int(duration)
            else:
                self._attr_extra_state_attributes["duration"] = 0
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Unexpected recording duration feedback: %s, error: %s", params, err
            )


class WebexCEStreamingSensor(SensorEntity):
    """Representation of streaming sensor with status and duration."""

    _attr_has_entity_name = True
    _attr_translation_key = "streaming"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, client, device_info: DeviceInfo) -> None:
        """Initialize the sensor."""
        self._client = client
        self._attr_device_info = device_info
        serial = next(iter(device_info["identifiers"]))[1]
        self._attr_unique_id = f"{serial}_streaming"
        self._attr_native_value = "No"
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to device feedback when added to hass."""
        await super().async_added_to_hass()
        # Subscribe to both status and duration
        await self._client.subscribe_feedback(
            f"{self.unique_id}_status",
            ["Status", "Streaming", "Status"],
            self._handle_status_feedback,
        )
        await self._client.subscribe_feedback(
            f"{self.unique_id}_duration",
            ["Status", "Streaming", "Duration"],
            self._handle_duration_feedback,
        )

    @callback
    def _handle_status_feedback(self, params: dict[str, Any], feedback_id: str) -> None:
        """Handle status feedback from the device."""
        try:
            status = (
                params.get("Status", {}).get("Streaming", {}).get("Status", "Inactive")
            )
            # Set state to Yes/No based on streaming status
            self._attr_native_value = (
                "Yes" if status in ("Streaming", "Active") else "No"
            )
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug(
                "Unexpected streaming status feedback: %s, error: %s", params, err
            )

    @callback
    def _handle_duration_feedback(
        self, params: dict[str, Any], feedback_id: str
    ) -> None:
        """Handle duration feedback from the device."""
        try:
            duration = params.get("Status", {}).get("Streaming", {}).get("Duration")
            if duration is not None:
                self._attr_extra_state_attributes["duration"] = int(duration)
            else:
                self._attr_extra_state_attributes["duration"] = 0
            self.async_write_ha_state()
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Unexpected streaming duration feedback: %s, error: %s", params, err
            )

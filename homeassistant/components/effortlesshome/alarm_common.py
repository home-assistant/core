"""Initialization of alarm_control_panel platform."""

import json
import logging

from homeassistant.core import HomeAssistant

from . import const
from oasira import OasiraAPIClient, OasiraAPIError
from .const import (
    ALARM_TYPE_MED_ALERT,
    ALARM_TYPE_MONITORING,
    ALARM_TYPE_SECURITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PendingAlarm:
    def __init__(
        self,
        hass: HomeAssistant,
        open_sensors: dict,
        sensor_device_class: str,
        sensor_device_name: str,
        alarmtype: str,
    ) -> None:
        # Initialize the class with provided parameters
        self.open_sensors = open_sensors
        self.sensor_device_class = sensor_device_class
        self.sensor_device_name = sensor_device_name
        self.hass = hass
        self.alarmtype = alarmtype


class PendingAlarmComponent:
    # Class-level property to hold the pending alarm instance
    _pendingalarm = None

    @classmethod
    def set_pendingalarm(cls, alarm: PendingAlarm) -> None:
        cls._pendingalarm = alarm

    @classmethod
    def get_pendingalarm(cls):
        return cls._pendingalarm


def _is_firebase_token_error(err: Exception) -> bool:
    """Check if the error is related to Firebase token expiration or invalidation."""
    msg = str(err).lower()
    status = getattr(err, "status", None) or getattr(err, "status_code", None)

    # Check for HTTP 401 status
    if status == 401:
        return True

    # Check for explicit Firebase token errors
    if "firebase token" in msg and ("expired" in msg or "invalid" in msg):
        return True

    # Check for generic 401 with token mention
    if "status 401" in msg and "token" in msg:
        return True

    # Check for common Firebase auth error patterns
    if any(
        pattern in msg
        for pattern in [
            "unauthorized",
            "invalid authentication",
            "token has expired",
            "invalid token",
            "authentication failed",
        ]
    ):
        return True

    return False


def _extract_error_json(err: Exception) -> dict | None:
    message = str(err)
    marker = ":"
    if marker not in message:
        return None

    payload = message.split(marker, 1)[1].strip()
    if not payload.startswith("{"):
        return None

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def _refresh_id_token(hass: HomeAssistant) -> bool:
    refresh_token = hass.data.get(DOMAIN, {}).get("refresh_token")
    if not refresh_token:
        _LOGGER.warning("No refresh token available - cannot refresh Firebase token")
        return False

    try:
        async with OasiraAPIClient() as api_client:
            result = await api_client.firebase_refresh_token(refresh_token)

        new_id_token = result.get("idToken")
        new_refresh_token = result.get("refreshToken") or refresh_token

        if not new_id_token:
            _LOGGER.error("Failed to refresh Firebase token - no idToken in response")
            return False

        hass.data[DOMAIN]["id_token"] = new_id_token
        hass.data[DOMAIN]["refresh_token"] = new_refresh_token

        entry = hass.data[DOMAIN].get("config_entry")
        if entry is not None:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    "id_token": new_id_token,
                    "refresh_token": new_refresh_token,
                },
            )

        _LOGGER.info("✅ Firebase ID token refreshed successfully")
        return True

    except OasiraAPIError as e:
        _LOGGER.error("Failed to refresh Firebase token: %s", e)
        return False
    except Exception as e:
        _LOGGER.exception("Unexpected error refreshing Firebase token: %s", e)
        return False


async def async_creatependingalarm(
    hass: HomeAssistant, alarmtype: str, open_sensors: dict | None = None
) -> None:
    _LOGGER.debug("in create pending alarm")

    if open_sensors is not None:
        _LOGGER.debug("open_sensors" + str(open_sensors))

    sensor_device_class = None
    sensor_device_name = None

    if open_sensors is not None:
        for entity_id in open_sensors:
            devicestate = hass.states.get(entity_id)
            if devicestate and devicestate.attributes.get("friendly_name"):
                sensor_device_name = devicestate.attributes["friendly_name"]
            if devicestate and devicestate.attributes.get("device_class"):
                sensor_device_class = devicestate.attributes["device_class"]

    if sensor_device_class is not None:
        _LOGGER.debug("sensor_device_class" + sensor_device_class)

    if sensor_device_name is not None:
        _LOGGER.debug("sensor_device_name" + sensor_device_name)

    alarm = PendingAlarm(
        hass, open_sensors, sensor_device_class, sensor_device_name, alarmtype
    )

    PendingAlarmComponent.set_pendingalarm(alarm)

    hass.data[DOMAIN]["alarm_id"] = "pending"
    hass.data[DOMAIN]["alarmcreatemessage"] = "pending"
    hass.data[DOMAIN]["alarmownerid"] = "pending"
    hass.data[DOMAIN]["alarmstatus"] = "PENDING"
    hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.pending"
    hass.data[DOMAIN]["alarmtype"] = alarmtype


async def async_confirmpendingalarm(hass: HomeAssistant):
    """Call the API to confirm pending alarm."""
    _LOGGER.debug("in confirm pending alarm")

    pendingAlarm = PendingAlarmComponent.get_pendingalarm()

    _LOGGER.info("Pending Alarm: %s", pendingAlarm)

    if pendingAlarm is None:
        return

    if pendingAlarm.alarmtype == ALARM_TYPE_MONITORING:
        await async_createmonitoringalarm(pendingAlarm)
    elif pendingAlarm.alarmtype == ALARM_TYPE_SECURITY:
        await async_createsecurityalarm(pendingAlarm)
    elif pendingAlarm.alarmtype == ALARM_TYPE_MED_ALERT:
        await async_createmedicalalertalarm(pendingAlarm)


async def async_createsecurityalarm(pendingAlarm):
    """Call the API to create a security alarm."""
    _LOGGER.debug("in create security alarm")

    _LOGGER.info("Pending Alarm: %s", pendingAlarm)

    if pendingAlarm is None:
        return

    hass = pendingAlarm.hass

    _LOGGER.info("Pending Alarm HASS: %s", pendingAlarm.hass)

    # Check for feature id 3 in plan features
    plan_features = hass.data[DOMAIN].get("plan_features")

    # TODO: Jermie - fix api and remove this workaround
    has_feature_3 = True  # False

    if plan_features:
        # plan_features may be a dict with a 'features' key or a list of dicts
        features = (
            plan_features.get("features") if isinstance(plan_features, dict) else None
        )
        if features and isinstance(features, list):
            has_feature_3 = any(
                (isinstance(f, dict) and f.get("feature_id") == 3)
                or (isinstance(f, int) and f == 3)
                for f in features
            )
        elif isinstance(plan_features, list):
            has_feature_3 = any(
                (isinstance(f, dict) and f.get("feature_id") == 3)
                or (isinstance(f, int) and f == 3)
                for f in plan_features
            )
    if not has_feature_3:
        _LOGGER.info("No Active Security Plan (feature id 3 not present)")
        return

    systemid = hass.data[DOMAIN].get("systemid")

    _LOGGER.info("System ID: %s", hass.data[DOMAIN].get("systemid"))
    _LOGGER.info("Email Address: %s", hass.data[DOMAIN].get("username"))

    # Populate alarm_data with the actual triggering sensor
    alarm_data = {
        "sensor_device_class": pendingAlarm.sensor_device_class or "unknown",
        "sensor_device_name": pendingAlarm.sensor_device_name or "unknown",
    }

    _LOGGER.info("Calling create monitoring alarm API with payload: %s", alarm_data)

    id_token = hass.data[DOMAIN].get("id_token")

    async with OasiraAPIClient(
        system_id=systemid,
        id_token=id_token,
    ) as api_client:
        try:
            result = await api_client.create_security_alarm(alarm_data)
            _LOGGER.info("API response content: %s", result)

            hass.data[DOMAIN]["alarm_id"] = result.get("AlarmID")
            hass.data[DOMAIN]["alarmcreatemessage"] = result.get("Message")
            hass.data[DOMAIN]["alarmownerid"] = result.get("OwnerID")
            hass.data[DOMAIN]["alarmstatus"] = result.get("Status")
            hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
            hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_SECURITY

            PendingAlarmComponent.set_pendingalarm(None)
        except OasiraAPIError as e:
            if _is_firebase_token_error(e) and await _refresh_id_token(hass):
                id_token = hass.data[DOMAIN].get("id_token")
                async with OasiraAPIClient(
                    system_id=systemid,
                    id_token=id_token,
                ) as retry_client:
                    try:
                        result = await retry_client.create_security_alarm(alarm_data)
                        _LOGGER.info("API response content: %s", result)

                        hass.data[DOMAIN]["alarm_id"] = result.get("AlarmID")
                        hass.data[DOMAIN]["alarmcreatemessage"] = result.get("Message")
                        hass.data[DOMAIN]["alarmownerid"] = result.get("OwnerID")
                        hass.data[DOMAIN]["alarmstatus"] = result.get("Status")
                        hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
                        hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_SECURITY

                        PendingAlarmComponent.set_pendingalarm(None)
                        return
                    except OasiraAPIError as retry_error:
                        _LOGGER.error(
                            "Failed to create security alarm after refresh: %s",
                            retry_error,
                        )
                        return

            _LOGGER.error("Failed to create security alarm: %s", e)


async def async_createmonitoringalarm(pendingAlarm):
    """Call the API to create a monitoring alarm."""

    _LOGGER.debug("in create monitoring alarm")

    if pendingAlarm is None:
        return

    hass = pendingAlarm.hass

    # Check for feature id 4 in plan features
    plan_features = hass.data[DOMAIN].get("plan_features")
    has_feature_4 = False
    if plan_features:
        features = (
            plan_features.get("features") if isinstance(plan_features, dict) else None
        )
        if features and isinstance(features, list):
            has_feature_4 = any(
                (isinstance(f, dict) and f.get("feature_id") == 4)
                or (isinstance(f, int) and f == 4)
                for f in features
            )
        elif isinstance(plan_features, list):
            has_feature_4 = any(
                (isinstance(f, dict) and f.get("feature_id") == 4)
                or (isinstance(f, int) and f == 4)
                for f in plan_features
            )
    if not has_feature_4:
        _LOGGER.info("No Active Monitoring Plan (feature id 4 not present)")
        return

    systemid = hass.data[DOMAIN].get("systemid")
    id_token = hass.data[DOMAIN].get("id_token")

    # Populate alarm_data with the actual triggering sensor
    alarm_data = {
        "sensor_device_class": pendingAlarm.sensor_device_class or "unknown",
        "sensor_device_name": pendingAlarm.sensor_device_name or "unknown",
    }

    _LOGGER.info("Calling create medical alarm API with payload: %s", alarm_data)

    async with OasiraAPIClient(
        system_id=systemid,
        id_token=id_token,
    ) as api_client:
        try:
            result = await api_client.create_monitoring_alarm(alarm_data)
            _LOGGER.debug("API response content: %s", result)

            hass.data[DOMAIN]["alarm_id"] = result["AlarmID"]
            hass.data[DOMAIN]["alarmcreatemessage"] = result["Message"]
            hass.data[DOMAIN]["alarmownerid"] = result["OwnerID"]
            hass.data[DOMAIN]["alarmstatus"] = result["Status"]
            hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
            hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_MONITORING

            PendingAlarmComponent.set_pendingalarm(None)
        except OasiraAPIError as e:
            if _is_firebase_token_error(e) and await _refresh_id_token(hass):
                id_token = hass.data[DOMAIN].get("id_token")
                async with OasiraAPIClient(
                    system_id=systemid,
                    id_token=id_token,
                ) as retry_client:
                    try:
                        result = await retry_client.create_monitoring_alarm(alarm_data)
                        _LOGGER.debug("API response content: %s", result)

                        hass.data[DOMAIN]["alarm_id"] = result["AlarmID"]
                        hass.data[DOMAIN]["alarmcreatemessage"] = result["Message"]
                        hass.data[DOMAIN]["alarmownerid"] = result["OwnerID"]
                        hass.data[DOMAIN]["alarmstatus"] = result["Status"]
                        hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
                        hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_MONITORING

                        PendingAlarmComponent.set_pendingalarm(None)
                        return
                    except OasiraAPIError as retry_error:
                        _LOGGER.error(
                            "Failed to create monitoring alarm after refresh: %s",
                            retry_error,
                        )
                        return

            _LOGGER.error("Failed to create monitoring alarm: %s", e)


async def async_createmedicalalertalarm(pendingAlarm):
    """Call the API to create a medical alarm."""
    _LOGGER.debug("in create medical alert alarm")

    if pendingAlarm is None:
        return

    hass = pendingAlarm.hass

    # Check for feature id 5 in plan features
    plan_features = hass.data[DOMAIN].get("plan_features")
    has_feature_5 = False
    if plan_features:
        features = (
            plan_features.get("features") if isinstance(plan_features, dict) else None
        )
        if features and isinstance(features, list):
            has_feature_5 = any(
                (isinstance(f, dict) and f.get("feature_id") == 5)
                or (isinstance(f, int) and f == 5)
                for f in features
            )
        elif isinstance(plan_features, list):
            has_feature_5 = any(
                (isinstance(f, dict) and f.get("feature_id") == 5)
                or (isinstance(f, int) and f == 5)
                for f in plan_features
            )
    if not has_feature_5:
        _LOGGER.info("No Active Medical Alert Alarm Plan (feature id 5 not present)")
        return

    systemid = hass.data[DOMAIN].get("systemid")

    alarm_data = {
        "sensor_device_class": "medical",
        "sensor_device_name": "medical alert",
    }

    _LOGGER.info("Calling create medical alarm API with payload: %s", alarm_data)

    id_token = hass.data[DOMAIN].get("id_token")

    async with OasiraAPIClient(
        system_id=systemid,
        id_token=id_token,
    ) as api_client:
        try:
            result = await api_client.create_medical_alarm(alarm_data)
            _LOGGER.debug("API response content: %s", result)

            hass.data[DOMAIN]["alarm_id"] = result["AlarmID"]
            hass.data[DOMAIN]["alarmcreatemessage"] = result["Message"]
            hass.data[DOMAIN]["alarmownerid"] = result["OwnerID"]
            hass.data[DOMAIN]["alarmstatus"] = result["Status"]
            hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
            hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_MED_ALERT

            PendingAlarmComponent.set_pendingalarm(None)
        except OasiraAPIError as e:
            if _is_firebase_token_error(e) and await _refresh_id_token(hass):
                id_token = hass.data[DOMAIN].get("id_token")
                async with OasiraAPIClient(
                    system_id=systemid,
                    id_token=id_token,
                ) as retry_client:
                    try:
                        result = await retry_client.create_medical_alarm(alarm_data)
                        _LOGGER.debug("API response content: %s", result)

                        hass.data[DOMAIN]["alarm_id"] = result["AlarmID"]
                        hass.data[DOMAIN]["alarmcreatemessage"] = result["Message"]
                        hass.data[DOMAIN]["alarmownerid"] = result["OwnerID"]
                        hass.data[DOMAIN]["alarmstatus"] = result["Status"]
                        hass.data[DOMAIN]["alarmlasteventtype"] = "alarm.status.created"
                        hass.data[DOMAIN]["alarmtype"] = ALARM_TYPE_MED_ALERT

                        PendingAlarmComponent.set_pendingalarm(None)
                        return
                    except OasiraAPIError as retry_error:
                        _LOGGER.error(
                            "Failed to create medical alarm after refresh: %s",
                            retry_error,
                        )
                        return

            _LOGGER.error("Failed to create medical alarm: %s", e)


async def async_cancelalarm(hass: HomeAssistant):
    """Call the API to create a medical alarm."""
    _LOGGER.debug("in cancel alarm")

    alarmstate = hass.data[DOMAIN]["alarm_id"]

    if alarmstate is not None and alarmstate != "":
        alarmstatus = hass.data[DOMAIN]["alarmstatus"]

        if alarmstatus == "PENDING":
            PendingAlarmComponent.set_pendingalarm(None)

            hass.data[DOMAIN]["alarm_id"] = ""
            hass.data[DOMAIN]["alarmcreatemessage"] = ""
            hass.data[DOMAIN]["alarmownerid"] = ""
            hass.data[DOMAIN]["alarmstatus"] = ""
            hass.data[DOMAIN]["alarmlasteventtype"] = ""
            hass.data[DOMAIN]["alarmtype"] = ""

            return None

        if alarmstatus == "ACTIVE":
            alarmid = hass.data[DOMAIN]["alarm_id"]
            _LOGGER.debug("alarm id =" + alarmid)

            systemid = hass.data[DOMAIN].get("systemid")
            id_token = hass.data[DOMAIN].get("id_token")

            _LOGGER.info("Calling cancel alarm API")

            async with OasiraAPIClient(
                system_id=systemid,
                id_token=id_token,
            ) as api_client:
                try:
                    result = await api_client.cancel_alarm(alarmid)
                    _LOGGER.debug("API response content: %s", result)

                    # {"status":"CANCELED","created_at":"2024-09-21T15:13:24.895Z"}
                    alarmstatus = result["status"]

                    hass.data[DOMAIN]["alarm_id"] = ""
                    hass.data[DOMAIN]["alarmcreatemessage"] = ""
                    hass.data[DOMAIN]["alarmownerid"] = ""
                    hass.data[DOMAIN]["alarmstatus"] = ""
                    hass.data[DOMAIN]["alarmlasteventtype"] = alarmstatus
                    hass.data[DOMAIN]["alarmtype"] = ""

                    await hass.services.async_call(
                        DOMAIN,
                        "getalarmstatusservice",
                        {},
                        blocking=False,
                    )

                    return result
                except OasiraAPIError as e:
                    message = str(e).lower()
                    if "status 201" in message:
                        payload = _extract_error_json(e)
                        if payload and payload.get("status") == "CANCELED":
                            alarmstatus = payload.get("status")
                            hass.data[DOMAIN]["alarm_id"] = ""
                            hass.data[DOMAIN]["alarmcreatemessage"] = ""
                            hass.data[DOMAIN]["alarmownerid"] = ""
                            hass.data[DOMAIN]["alarmstatus"] = ""
                            hass.data[DOMAIN]["alarmlasteventtype"] = alarmstatus
                            hass.data[DOMAIN]["alarmtype"] = ""
                            await hass.services.async_call(
                                DOMAIN,
                                "getalarmstatusservice",
                                {},
                                blocking=False,
                            )
                            return payload

                    _LOGGER.error("Failed to cancel alarm: %s", e)
                    return None
    return None


async def async_getalarmstatus(hass: HomeAssistant):
    """Call the API to create a medical alarm."""
    _LOGGER.debug("in get alarm status")

    alarmstate = hass.data[DOMAIN]["alarm_id"]

    if alarmstate is not None and alarmstate != "":
        alarmid = hass.data[DOMAIN]["alarm_id"]

        if alarmid == "pending":
            return None

        systemid = hass.data[DOMAIN]["systemid"]
        id_token = hass.data[DOMAIN].get("id_token")

        _LOGGER.info("Calling get alarm status API")

        async with OasiraAPIClient(
            system_id=systemid,
            id_token=id_token,
        ) as api_client:
            try:
                result = await api_client.get_alarm_status(alarmid)
                _LOGGER.debug("API response content: %s", result)

                alarmstatus = result["status"]
                hass.states.async_set(DOMAIN + ".alarmstatus", alarmstatus)

                return result
            except OasiraAPIError as e:
                _LOGGER.error("Failed to get alarm status: %s", e)
                return None
    return None

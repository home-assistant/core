"""PyNest API Client."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any, TypeVar
from urllib.parse import urljoin
import uuid

from aiohttp import (
    ClientError,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    FormData,
)
import google.protobuf.any_pb2
from google.protobuf.duration_pb2 import Duration  # pylint: disable=no-name-in-module
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp  # pylint: disable=no-name-in-module

from .enums import BucketType, Environment, StructureMode, ThermostatHvacMode
from .exceptions import (
    BadCredentialsException,
    BadGatewayException,
    EmptyResponseException,
    GatewayTimeoutException,
    NonRetryablePynestException,
    NotAuthenticatedException,
    PynestException,
)
from .models import (
    Bucket,
    FirstDataAPIResponse,
    GoogleAuthResponse,
    NestAuthResponse,
    NestCamera,
    NestDevice,
    NestEnvironment,
    NestHeatLink,
    NestLock,
    NestProtect,
    NestSession,
    NestStructure,
    NestTempSensor,
    NestThermostat,
)
from .protobuf_gen.nest.trait import (
    audio_pb2 as nest_audio_pb2,
    history_pb2 as nest_history_pb2,
    hvac_pb2 as nest_hvac_pb2,
    located_pb2 as nest_located_pb2,
    occupancy_pb2 as nest_occupancy_pb2,
    safety_pb2 as nest_safety_pb2,
    sensor_pb2 as nest_sensor_pb2,
    structure_pb2 as nest_structure_pb2,
    ui_pb2 as nest_ui_pb2,
)
from .protobuf_gen.nest.trait.product import (
    camera_pb2 as nest_camera_pb2,
    doorbell_pb2 as nest_doorbell_pb2,
    protect_pb2 as nest_protect_pb2,
)
from .protobuf_gen.nestlabs.gateway import v1_pb2, v2_pb2
from .protobuf_gen.weave import common_pb2 as weave_common_pb2
from .protobuf_gen.weave.trait import (
    description_pb2 as weave_description_pb2,
    heartbeat_pb2 as weave_heartbeat_pb2,
    power_pb2 as weave_power_pb2,
    security_pb2 as weave_security_pb2,
)

_NON_RETRYABLE_CODES = frozenset(
    {
        3,  # INVALID_ARGUMENT: Client specified an invalid argument.
        5,  # NOT_FOUND: Some requested entity was not found.
        6,  # ALREADY_EXISTS: Entity that a client attempted to create already exists.
        7,  # PERMISSION_DENIED: Caller does not have permission to execute the method.
        9,  # FAILED_PRECONDITION: Operation rejected because the system is not in a required state.
        11,  # OUT_OF_RANGE: Operation was attempted past the valid range.
        12,  # UNIMPLEMENTED: Operation is not implemented or not supported/enabled.
        15,  # DATA_LOSS: Unrecoverable data loss or corruption.
        # Intentionally excluded to be able to raise NotAuthenticatedException
        # 16,  # UNAUTHENTICATED: The request does not have valid authentication credentials for the operation
    }
)

# Needed to get the "STRUCTURE_" key (see _parse_structure in parser.py)
_OBSERVER_ALWAYS_INCLUDE_TRAITS = (nest_occupancy_pb2.StructureModeTrait,)

# Lock-specific traits
_OBSERVE_LOCK_TRAITS = (
    # Security (Locks)
    weave_security_pb2.BoltLockTrait,
    weave_security_pb2.BoltLockSettingsTrait,
    weave_security_pb2.BoltLockCapabilitiesTrait,
    weave_security_pb2.TamperTrait,
    # Power (for Locks)
    weave_power_pb2.BatteryPowerSourceTrait,
    # Description / Identity (for Locks)
    weave_description_pb2.DeviceIdentityTrait,
    weave_description_pb2.LabelSettingsTrait,
    weave_heartbeat_pb2.LivenessTrait,
    nest_located_pb2.DeviceLocatedSettingsTrait,
)

# Thermostat-specific traits
_OBSERVE_THERMOSTAT_TRAITS = (
    # Thermostat / HVAC
    nest_hvac_pb2.HvacControlTrait,
    nest_hvac_pb2.KryptoniteObservedBeaconTrait,
    # Commented out since it's unused and causes conflict on
    # labels ('heat_schedule_settings' and 'cool_schedule_settings')
    # that would need to be added in _LABEL_SPECIFIC_TRAITS.
    # nest_hvac_pb2.SetPointScheduleSettingsTrait,
    nest_hvac_pb2.RemoteComfortSensingSettingsTrait,
    nest_hvac_pb2.EquipmentSettingsTrait,
    nest_hvac_pb2.HvacEquipmentCapabilitiesTrait,
    nest_hvac_pb2.SeasonalSavingsSettingsTrait,
    nest_hvac_pb2.FanControlSettingsTrait,
    nest_hvac_pb2.FanControlCapabilitiesTrait,
    nest_hvac_pb2.TargetTemperatureSettingsTrait,
    nest_hvac_pb2.EcoModeTrait,
    nest_hvac_pb2.EcoModeStateTrait,
    nest_hvac_pb2.EcoModeSettingsTrait,
    nest_hvac_pb2.HumidityControlSettingsTrait,
    nest_hvac_pb2.DisplaySettingsTrait,
    nest_hvac_pb2.TemperatureLockSettingsTrait,
    nest_hvac_pb2.LeafTrait,
    nest_hvac_pb2.FilterReminderTrait,
    # Hot Water / Heat Link
    nest_hvac_pb2.HeatLinkTrait,
    nest_hvac_pb2.HotWaterTrait,
    nest_hvac_pb2.HotWaterSettingsTrait,
    # Sensors (Thermostat)
    nest_sensor_pb2.TemperatureTrait,
    nest_sensor_pb2.HumidityTrait,
    nest_sensor_pb2.BatteryVoltageTrait,
    # Description / Identity (for Thermostat)
    weave_description_pb2.DeviceIdentityTrait,
    weave_description_pb2.LabelSettingsTrait,
    weave_heartbeat_pb2.LivenessTrait,
    nest_located_pb2.DeviceLocatedSettingsTrait,
)

# Protect-specific traits
_OBSERVE_PROTECT_TRAITS = (
    # Sensors (Protect)
    nest_sensor_pb2.SmokeTrait,
    nest_sensor_pb2.CarbonMonoxideTrait,
    nest_sensor_pb2.BatteryVoltageTrait,
    nest_sensor_pb2.PassiveInfraredTrait,
    nest_sensor_pb2.AmbientLightTrait,
    # Protect
    nest_protect_pb2.AudioTestTrait,
    nest_protect_pb2.LegacyProtectDeviceInfoTrait,
    nest_protect_pb2.SelfTestTrait,
    nest_protect_pb2.ProtectDeviceInfoTrait,
    nest_protect_pb2.SafetySummaryTrait,
    nest_protect_pb2.NightTimePromiseTrait,
    nest_protect_pb2.NightTimePromiseSettingsTrait,
    nest_protect_pb2.LegacyProtectDeviceSettingsTrait,
    nest_protect_pb2.LegacyStructureSelfTestTrait,
    nest_ui_pb2.EnhancedPathlightSettingsTrait,
    nest_ui_pb2.EnhancedPathlightStateTrait,
    nest_ui_pb2.PathlightSettingsTrait,
    nest_safety_pb2.SafetyAlarmSmokeTrait,
    nest_safety_pb2.SafetyAlarmCOTrait,
    nest_safety_pb2.SafetyAlarmSettingsTrait,
    # Power (for Protect)
    weave_power_pb2.BatteryPowerSourceTrait,
    weave_power_pb2.PowerSourceTrait,
    # Description / Identity (for Protect)
    weave_description_pb2.DeviceIdentityTrait,
    weave_description_pb2.LabelSettingsTrait,
    weave_heartbeat_pb2.LivenessTrait,
    nest_located_pb2.DeviceLocatedSettingsTrait,
)

# Camera-specific traits
_OBSERVE_CAMERA_TRAITS = (
    # Camera
    nest_camera_pb2.StreamingProtocolTrait,
    nest_camera_pb2.RecordingToggleTrait,
    nest_camera_pb2.RecordingToggleSettingsTrait,
    nest_camera_pb2.DoorStateTrait,
    nest_camera_pb2.ActivityZoneSettingsTrait,
    nest_camera_pb2.ObservationTriggerSettingsTrait,
    nest_camera_pb2.CameraMigrationStatusTrait,
    nest_camera_pb2.UploadLiveImageTrait,
    nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait,
    nest_audio_pb2.MicrophoneSettingsTrait,
    weave_power_pb2.BatteryPowerSourceTrait,
    # Description / Identity (for Camera)
    weave_description_pb2.DeviceIdentityTrait,
    weave_description_pb2.LabelSettingsTrait,
    weave_heartbeat_pb2.LivenessTrait,
    nest_located_pb2.DeviceLocatedSettingsTrait,
)

# Structure-specific traits
_OBSERVE_STRUCTURE_TRAITS = (
    nest_occupancy_pb2.StructureModeTrait,
    # Structure
    nest_structure_pb2.StructureInfoTrait,
    nest_structure_pb2.StructureLocationTrait,
    nest_structure_pb2.HomeInfoSettingsTrait,
    nest_located_pb2.DeviceLocatedSettingsTrait,
    # Description / Identity (for Structure)
    weave_description_pb2.DeviceIdentityTrait,
    weave_description_pb2.LabelSettingsTrait,
    weave_heartbeat_pb2.LivenessTrait,
)

# All possible traits for parsing
_ALL_POSSIBLE_TRAITS = (
    _OBSERVER_ALWAYS_INCLUDE_TRAITS
    + _OBSERVE_PROTECT_TRAITS
    + _OBSERVE_CAMERA_TRAITS
    + _OBSERVE_THERMOSTAT_TRAITS
    + _OBSERVE_LOCK_TRAITS
    + _OBSERVE_STRUCTURE_TRAITS
)

_TRAIT_TYPE_TO_CLASS_MAP = {
    trait.DESCRIPTOR.full_name: trait for trait in _ALL_POSSIBLE_TRAITS
}

# Trait labels that should be stored by label in addition to descriptor_full_name.
# This is needed when the same trait type appears multiple times on a device
# under different labels (e.g. "current_temperature" vs "backplate_temperature"
# both use TemperatureTrait).
_LABEL_SPECIFIC_TRAITS: frozenset[str] = frozenset(
    {
        "backplate_temperature",
        "current_temperature",
        "battery_voltage_bank0",
        "battery_voltage_bank1",
    }
)

_USER_AGENT = "Nest/5.82.2 (iOScom.nestlabs.jasper.release) os=18.5"

_NEST_ENVIRONMENTS: dict[str, NestEnvironment] = {
    Environment.PRODUCTION: NestEnvironment(
        host="home.nest.com",
        camera_host="camera.home.nest.com",
        camera_cookie_name="website_2=",
        grpc_host="grpc-web.production.nest.com",
    ),
    Environment.FIELDTEST: NestEnvironment(
        host="home.ft.nest.com",
        camera_host="camera.home.ft.nest.com",
        camera_cookie_name="website_ft=",
        grpc_host="grpc-web.ft.nest.com",
    ),
}

# App launch API endpoint
_APP_LAUNCH_URL_FORMAT = "https://{host}/api/0.1/user/{user_id}/app_launch"
_NEST_AUTH_URL_JWT = "https://nestauthproxyservice-pa.googleapis.com/v1/issue_jwt"

# Legacy Nest account login
_LEGACY_LOGIN_URL_FORMAT = "https://webapi.{host}/api/v1/login.login_nest"

# Protobuf endpoints
_OBSERVE_ENDPOINT = "/nestlabs.gateway.v2.GatewayService/Observe"
_SEND_COMMAND_ENDPOINT = "/nestlabs.gateway.v1.ResourceApi/SendCommand"
_BATCH_UPDATE_ENDPOINT = "/nestlabs.gateway.v1.TraitBatchApi/BatchUpdateState"

_NESTLABS_TYPE_URL_PREFIX = "type.nestlabs.com/"

_NEST_REQUEST: dict[str, Any] = {
    "known_bucket_types": [
        BucketType.BUCKETS,
        BucketType.DELAYED_TOPAZ,
        BucketType.DEMAND_RESPONSE,
        BucketType.DEVICE,
        BucketType.DEVICE_ALERT_DIALOG,
        BucketType.GEOFENCE_INFO,
        BucketType.KRYPTONITE,
        BucketType.LINK,
        BucketType.MESSAGE,
        BucketType.MESSAGE_CENTER,
        BucketType.METADATA,
        BucketType.OCCUPANCY,
        BucketType.QUARTZ,
        BucketType.SAFETY,
        BucketType.RCS_SETTINGS,
        BucketType.SAFETY_SUMMARY,
        BucketType.SCHEDULE,
        BucketType.SHARED,
        BucketType.STRUCTURE,
        BucketType.STRUCTURE_METADATA,
        BucketType.TOPAZ,
        BucketType.TOPAZ_RESOURCE,
        BucketType.TRACK,
        BucketType.TRIP,
        BucketType.TUNEUPS,
        BucketType.USER,
        BucketType.USER_SETTINGS,
        BucketType.WHERE,
        BucketType.WIDGET_TRACK,
    ],
    "known_bucket_versions": [],
}

_SUBSCRIBE_TIMEOUT = 600  # seconds
_OBSERVE_TIMEOUT = 600  # seconds
_CONNECT_TIMEOUT = 60  # seconds
_PROTOBUF_COMMAND_TIMEOUT = 30  # seconds

_LOGGER = logging.getLogger(__package__)


# The _decode_varint helper function is required to find frame boundaries.
def _decode_varint(buffer: bytes | bytearray) -> tuple[int | None, int]:
    """Decodes a varint from the start of a buffer and returns the value and bytes read."""
    shift = 0
    result = 0
    bytes_read = 0
    while bytes_read < len(buffer):
        i = buffer[bytes_read]
        bytes_read += 1
        result |= (i & 0x7F) << shift
        shift += 7
        if not (i & 0x80):
            return result, bytes_read
    # If we run out of buffer before finding the end of the varint
    return None, 0


_T = TypeVar("_T", bound=Message)


def _get_trait_copy(traits: dict[str, Any] | None, trait_class: type[_T]) -> _T:
    """Get a copy of a trait from the cache or create a new one if missing."""
    if traits and (trait := traits.get(trait_class.DESCRIPTOR.full_name)):
        new_trait = trait_class()
        new_trait.CopyFrom(trait)
        return new_trait
    return trait_class()


class NestClient:
    """Interface class for the Nest API."""

    def __init__(
        self,
        session: ClientSession | None = None,
        field_test: bool = False,
        enable_protobuf_lock: bool = True,
        enable_protobuf_thermostat: bool = True,
        enable_protobuf_structure: bool = False,
        enable_protobuf_protect: bool = False,
        enable_protobuf_camera: bool = False,
    ) -> None:
        """Initialize NestClient."""
        self._session = session or ClientSession()
        self._environment = _NEST_ENVIRONMENTS[
            Environment.FIELDTEST if field_test else Environment.PRODUCTION
        ]
        self._nest_session: NestSession | None = None
        self._camera_session_token: str | None = None
        self._raw_data: dict[str, Any] = {}
        self._buckets_for_subscription: list[Bucket] = []
        self._resource_types: dict[str, str] = {}
        self._legacy_protobuf_events_warned: bool = False

        self._enable_protobuf_lock = enable_protobuf_lock
        self._enable_protobuf_thermostat = enable_protobuf_thermostat
        self._enable_protobuf_structure = enable_protobuf_structure
        self._enable_protobuf_protect = enable_protobuf_protect
        self._enable_protobuf_camera = enable_protobuf_camera

        # Build set of traits to observe based on flags
        self._observe_traits: set[type[Message]] = set()
        self._observe_traits.update(_OBSERVER_ALWAYS_INCLUDE_TRAITS)
        if enable_protobuf_protect:
            self._observe_traits.update(_OBSERVE_PROTECT_TRAITS)
        if enable_protobuf_camera:
            self._observe_traits.update(_OBSERVE_CAMERA_TRAITS)
        if enable_protobuf_thermostat:
            self._observe_traits.update(_OBSERVE_THERMOSTAT_TRAITS)
        if enable_protobuf_lock:
            self._observe_traits.update(_OBSERVE_LOCK_TRAITS)
        if enable_protobuf_structure:
            self._observe_traits.update(_OBSERVE_STRUCTURE_TRAITS)

    async def async_authenticate_with_google_credentials(
        self, issue_token: str, cookies: str
    ) -> NestSession:
        """Authenticate using Google issue token and cookies."""
        try:
            auth = await self._async_get_access_token_from_cookies(issue_token, cookies)
            return await self._async_authenticate(auth.access_token)
        except (ClientError, TimeoutError, PynestException) as err:
            _LOGGER.debug(
                "Expected error during Google credential authentication: %r", err
            )
            raise
        except Exception:
            _LOGGER.exception(
                "Unexpected error during Google credential authentication"
            )
            raise

    async def async_authenticate_with_nest_token(
        self, access_token: str
    ) -> NestSession:
        """Authenticate using a legacy Nest access token."""
        try:
            await self._async_get_camera_session_token(access_token)
            return await self._async_get_session(access_token)
        except (ClientError, TimeoutError, PynestException) as err:
            _LOGGER.debug(
                "Expected error during legacy Nest token authentication: %r", err
            )
            raise
        except Exception:
            _LOGGER.exception(
                "Unexpected error during legacy Nest token authentication"
            )
            raise

    async def _async_get_access_token_from_cookies(
        self, issue_token: str, cookies: str
    ) -> GoogleAuthResponse:
        """Get a Google access token."""
        _LOGGER.debug("Requesting Google access token from URL: %s", issue_token)
        async with self._session.get(
            issue_token,
            headers={
                "Sec-Fetch-Mode": "cors",
                "User-Agent": _USER_AGENT,
                "X-Requested-With": "XmlHttpRequest",
                "Referer": "https://accounts.google.com/o/oauth2/iframe",
                "cookie": cookies,
            },
        ) as response:
            result = await response.json()
            if "error" in result:
                raise BadCredentialsException(result.get("detail", result["error"]))
            return GoogleAuthResponse.from_dict(result)

    async def _async_authenticate(self, access_token: str) -> NestSession:
        """Start a new Nest session with a Google access token."""
        _LOGGER.debug(
            "Authenticating with Google access token at URL: %s", _NEST_AUTH_URL_JWT
        )
        async with self._session.post(
            _NEST_AUTH_URL_JWT,
            data=FormData(
                {
                    "embed_google_oauth_access_token": True,
                    "expire_after": "3600s",
                    "google_oauth_access_token": access_token,
                    "policy_id": "authproxy-oauth-policy",
                }
            ),
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": _USER_AGENT,
                "Referer": f"https://{self._environment.host}",
            },
        ) as response:
            result = await response.json()
            nest_auth = NestAuthResponse(**result)
            if not nest_auth.jwt:
                raise BadCredentialsException("Could not get JWT from Google token")
            return await self._async_get_session(nest_auth.jwt)

    async def _async_get_camera_session_token(self, access_token: str) -> None:
        """Get a session token for camera APIs (legacy only)."""
        url = _LEGACY_LOGIN_URL_FORMAT.format(host=self._environment.camera_host)
        headers = {
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"https://{self._environment.host}/",
            "Origin": f"https://{self._environment.host}",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        _LOGGER.debug("Requesting legacy camera session token from URL: %s", url)
        try:
            async with self._session.post(
                url,
                headers=headers,
                data=f"access_token={access_token}",
            ) as response:
                if not response.ok:
                    _LOGGER.error(
                        "Failed to get camera session token. Status: %s, Body: %s",
                        response.status,
                        await response.text(),
                    )
                    raise BadCredentialsException("Failed to get camera session token")

                login_data = await response.json()
                if not login_data.get("items"):
                    _LOGGER.error(
                        "Failed to get camera session token, response indicates error: %s",
                        login_data,
                    )
                    raise BadCredentialsException(
                        login_data.get("status_description", "Unknown")
                    )
                self._camera_session_token = login_data["items"][0]["session_token"]
                _LOGGER.debug("Successfully obtained legacy camera session token")
        except (KeyError, IndexError, TypeError, ContentTypeError) as err:
            _LOGGER.exception("Failed to parse camera session token from response")
            raise BadCredentialsException(
                "Could not extract camera session token"
            ) from err

    async def _async_get_session(self, token: str) -> NestSession:
        """Fetch main session data."""
        url = f"https://{self._environment.host}/session"
        _LOGGER.debug("Requesting main session from URL: %s", url)
        async with self._session.get(
            url,
            headers={"Authorization": f"Basic {token}", "User-Agent": _USER_AGENT},
        ) as response:
            if not response.ok:
                _LOGGER.error(
                    "Failed to get session. Status: %s, Body: %s",
                    response.status,
                    await response.text(),
                )
                raise BadCredentialsException(
                    f"Failed to get session: {response.status}"
                )
            nest_session_dict = await response.json()
            self._nest_session = NestSession.from_dict(nest_session_dict)
            _LOGGER.debug(
                "Successfully obtained main session for user %s",
                self._nest_session.email,
            )
            return self._nest_session

    def is_expired(self) -> bool:
        """Check if the current session is expired."""
        if not self._nest_session:
            return True
        # Note: For legacy Nest accounts, reverse-engineering of the camera
        # session token (JWT) confirms it is issued with an expiration identical
        # to the main Nest access token (~30 days). Checking the main session's
        # expiration is sufficient to rotate both tokens simultaneously.
        return self._nest_session.is_expired()

    def _filter_buckets(self, buckets: list[Bucket]) -> list[Bucket]:
        """Filter buckets based on enabled protobuf features."""
        excluded_keys = set()

        if self._enable_protobuf_thermostat:
            excluded_keys.update(
                {
                    BucketType.DEVICE,
                    BucketType.SHARED,
                    BucketType.LINK,
                    BucketType.TRACK,
                    BucketType.RCS_SETTINGS,
                    BucketType.DEMAND_RESPONSE,
                    BucketType.TUNEUPS,
                }
            )

        if self._enable_protobuf_protect:
            excluded_keys.update(
                {
                    BucketType.TOPAZ,
                    BucketType.TOPAZ_RESOURCE,
                    BucketType.WIDGET_TRACK,
                    BucketType.SAFETY,
                    BucketType.SAFETY_SUMMARY,
                }
            )

        if self._enable_protobuf_camera:
            excluded_keys.update({BucketType.QUARTZ})

        if self._enable_protobuf_structure:
            excluded_keys.update(
                {
                    BucketType.STRUCTURE,
                    BucketType.STRUCTURE_METADATA,
                    BucketType.METADATA,
                    BucketType.SCHEDULE,
                    BucketType.WHERE,
                }
            )

        # We keep only buckets that do NOT start with any of the excluded keys.
        # object_key format is typically "bucket_type.id" or just "bucket_type" for singletons.
        filtered = []
        for bucket in buckets:
            bucket_type = bucket.object_key.split(".")[0]
            if bucket_type in excluded_keys:
                continue
            # Handle cases where object_key equals the type exactly (less common for these types but possible)
            if bucket.object_key in excluded_keys:
                continue
            filtered.append(bucket)
        return filtered

    async def async_get_first_data(self) -> dict[str, Any]:
        """Get all initial data from the API."""
        if not self._nest_session:
            raise NotAuthenticatedException("No active Nest session.")

        url = _APP_LAUNCH_URL_FORMAT.format(
            host=self._environment.host, user_id=self._nest_session.userid
        )
        _LOGGER.debug("Requesting initial data from URL: %s", url)
        async with self._session.post(
            url,
            json=_NEST_REQUEST,
            headers={
                "Authorization": f"Basic {self._nest_session.access_token}",
                "X-nl-user-id": self._nest_session.userid,
                "X-nl-protocol-version": "1",
            },
        ) as response:
            result = await response.json()
            if "error" in result:
                raise PynestException(f"Error fetching first data: {result['error']}")

            response_data = FirstDataAPIResponse.from_dict(result)
            # Filter the buckets before subscribing
            self._buckets_for_subscription = self._filter_buckets(
                response_data.updated_buckets
            )
            self._raw_data = {
                bucket.object_key: bucket for bucket in self._buckets_for_subscription
            }
            _LOGGER.debug(
                "Successfully fetched initial data with %d buckets",
                len(self._raw_data),
            )
            return {
                bucket.object_key: bucket.value
                for bucket in self._buckets_for_subscription
            }

    async def async_subscribe_for_updates(self) -> dict[str, dict[str, Any]]:
        """Subscribe for data updates (long poll)."""
        if not self._nest_session:
            raise NotAuthenticatedException("No active Nest session.")

        objects: list[dict[str, str | int]] = [
            {
                "object_key": b.object_key,
                "object_revision": b.object_revision,
                "object_timestamp": b.object_timestamp,
            }
            for b in self._buckets_for_subscription
        ]
        url = f"{self._nest_session.urls.transport_url}/v6/subscribe"
        _LOGGER.debug("Subscribing for data updates from URL: %s", url)
        async with self._session.post(
            url,
            timeout=ClientTimeout(total=_SUBSCRIBE_TIMEOUT, connect=_CONNECT_TIMEOUT),
            json={"objects": objects, "timeout": _SUBSCRIBE_TIMEOUT},
            headers={
                "Authorization": f"Basic {self._nest_session.access_token}",
                "X-nl-user-id": self._nest_session.userid,
                "X-nl-protocol-version": "1",
            },
        ) as response:
            _LOGGER.debug("Subscriber response status: %s", response.status)
            if response.status == 401:
                raise NotAuthenticatedException
            if response.status == 504:
                raise GatewayTimeoutException
            if response.status == 502:
                raise BadGatewayException
            if response.content_length == 0:
                raise EmptyResponseException
            try:
                result = await response.json()
            except ContentTypeError as err:
                text = await response.text()
                _LOGGER.error("Subscriber content error: %s", text)
                raise PynestException(f"Subscriber error: {text}") from err

            updates: dict[str, dict[str, Any]] = {}
            for bucket_data in result.get("objects", []):
                bucket = Bucket.from_dict(bucket_data)
                # Verify we actually want this update (extra safety)
                if not self._filter_buckets([bucket]):
                    continue
                updates[bucket.object_key] = bucket.value
                for existing_bucket in self._buckets_for_subscription:
                    if existing_bucket.object_key == bucket.object_key:
                        existing_bucket.object_revision = bucket.object_revision
                        existing_bucket.object_timestamp = bucket.object_timestamp
                        break
            return updates

    async def _async_update_objects(
        self, objects_to_update: list[dict[str, Any]]
    ) -> None:
        """Send updates to the Nest API."""
        if not self._nest_session:
            raise NotAuthenticatedException("No active Nest session.")

        url = f"{self._nest_session.urls.transport_url}/v6/put"
        _LOGGER.debug("Updating objects via URL %s: %s", url, objects_to_update)

        async def _do_post():
            async with self._session.post(
                url,
                json={"objects": objects_to_update},
                headers={
                    "Authorization": f"Basic {self._nest_session.access_token}",
                    "X-nl-user-id": self._nest_session.userid,
                    "X-nl-protocol-version": "1",
                },
            ) as response:
                if response.status in (401, 403):
                    raise NotAuthenticatedException(
                        f"Authentication failed: {response.status}"
                    )
                if not response.ok:
                    if 400 <= response.status < 500 and response.status not in (
                        401,
                        403,
                        429,
                    ):
                        raise PynestException(f"BAD_REQUEST: {await response.text()}")
                    raise PynestException(
                        f"Error updating objects: {await response.text()}"
                    )

        for attempt in range(3):
            try:
                await _do_post()
            except (ClientError, TimeoutError, PynestException) as err:
                if (
                    isinstance(err, NotAuthenticatedException)
                    or "BAD_REQUEST:" in str(err)
                    or attempt == 2
                ):
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
            else:
                return

    async def _async_set_thermostat_property(
        self, object_key: str, data: dict[str, Any]
    ) -> None:
        """Set properties for a thermostat."""
        device_id = object_key.split(".")[1]

        # Translate generic 'hvac_mode' key to legacy API's 'target_temperature_type'
        if "hvac_mode" in data:
            data["target_temperature_type"] = data.pop("hvac_mode")

        # Translate semantic exit_eco flag to legacy REST eco payload
        if data.pop("exit_eco", None):
            data["eco"] = {"mode": "schedule"}

        shared_properties = {
            "target_temperature",
            "target_temperature_low",
            "target_temperature_high",
            "target_temperature_type",
        }
        shared_payload = {k: v for k, v in data.items() if k in shared_properties}
        device_payload = {k: v for k, v in data.items() if k not in shared_properties}

        objects_to_update = []
        if shared_payload:
            shared_payload["target_change_pending"] = True
            objects_to_update.append(
                {
                    "object_key": f"shared.{device_id}",
                    "op": "MERGE",
                    "value": shared_payload,
                }
            )
        if device_payload:
            objects_to_update.append(
                {"object_key": object_key, "op": "MERGE", "value": device_payload}
            )

        if objects_to_update:
            await self._async_update_objects(objects_to_update)

    async def _async_set_generic_property(
        self, object_key: str, data: dict[str, Any]
    ) -> None:
        """Set a property on a generic device."""
        await self._async_update_objects(
            [{"object_key": object_key, "op": "MERGE", "value": data}]
        )

    async def _async_set_heatlink_property(
        self,
        device: NestHeatLink,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a Heat Link."""
        if (
            device.associated_thermostat_object_key
            and "DEVICE_" in device.associated_thermostat_object_key
        ):
            await self._async_set_protobuf_heatlink_property(
                device, data, current_traits
            )
            return

        if not device.associated_thermostat_object_key:
            return

        payload = data.copy()

        # Legacy API does not support hot_water_mode directly
        payload.pop("hot_water_mode", None)

        if "hot_water_boost" in payload:
            duration_seconds = payload.pop("hot_water_boost_duration", 1800)
            is_boost = payload.pop("hot_water_boost")
            if is_boost:
                end_timestamp = int(time.time()) + duration_seconds
            else:
                end_timestamp = 0
            payload["hot_water_boost_time_to_end"] = end_timestamp
            payload["hot_water_active"] = is_boost

        if payload:
            await self._async_set_generic_property(
                device.associated_thermostat_object_key, payload
            )

    async def _async_set_protobuf_heatlink_property(
        self,
        device: NestHeatLink,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a Heat Link via Protobuf."""
        if not device.associated_thermostat_object_key:
            return

        hot_water_settings_trait = _get_trait_copy(
            current_traits, nest_hvac_pb2.HotWaterSettingsTrait
        )
        update_required = False

        if "hot_water_boost" in data:
            update_required = True
            is_boost = data["hot_water_boost"]
            # Use provided duration or default to 30 mins (1800s)
            duration_seconds = (
                data.get("hot_water_boost_duration", 1800) if is_boost else 0
            )

            # Calculate end time
            end_seconds = int(time.time()) + duration_seconds if is_boost else 0
            end_ts = Timestamp()
            end_ts.FromSeconds(end_seconds)

            hot_water_settings_trait.boostTimerEnd.CopyFrom(end_ts)

        if "hot_water_temperature" in data:
            update_required = True
            hot_water_settings_trait.temperature.value = float(
                data["hot_water_temperature"]
            )

        if "hot_water_mode" in data:
            update_required = True
            mode_val = data["hot_water_mode"]  # This is a string "schedule" or "off"

            pb_mode = (
                nest_hvac_pb2.HotWaterSettingsTrait.HotWaterMode.HOT_WATER_MODE_OFF
            )
            if mode_val == "schedule":
                pb_mode = nest_hvac_pb2.HotWaterSettingsTrait.HotWaterMode.HOT_WATER_MODE_SCHEDULE

            hot_water_settings_trait.mode = pb_mode

        if "hot_water_away_enabled" in data:
            update_required = True
            hot_water_settings_trait.structureModeFollowEnabled = data[
                "hot_water_away_enabled"
            ]

        if update_required:
            any_proto = google.protobuf.any_pb2.Any()
            # Note: Hot Water traits are usually on the thermostat resource
            any_proto.Pack(
                hot_water_settings_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.associated_thermostat_object_key,
                    traitLabel="hot_water_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

    async def _async_set_structure_property(
        self, device: NestStructure, data: dict[str, Any]
    ) -> None:
        """Set properties for a Nest Structure (Home/Away)."""
        if "mode" in data:
            mode_map = {
                StructureMode.HOME: nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_HOME,
                StructureMode.AWAY: nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_AWAY,
                StructureMode.VACATION: nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_VACATION,
                StructureMode.SLEEP: nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_SLEEP,
            }
            target_mode = mode_map.get(data["mode"])
            if target_mode is None:
                raise PynestException(f"Invalid structure mode: {data['mode']}")

            command = v1_pb2.ResourceCommand(traitLabel="structure_mode")
            command.command.Pack(
                nest_occupancy_pb2.StructureModeTrait.StructureModeChangeRequest(
                    structureMode=target_mode,
                    reason=nest_occupancy_pb2.StructureModeTrait.StructureModeReason.STRUCTURE_MODE_REASON_EXPLICIT_INTENT,
                ),
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )
            await self._async_send_command(device, command)

    def _get_protobuf_headers(self) -> dict[str, str]:
        """Get headers for protobuf API requests."""
        if not self._nest_session:
            raise NotAuthenticatedException(
                "No active Nest session for protobuf command."
            )
        return {
            "Authorization": f"Basic {self._nest_session.access_token}",
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/x-protobuf",
            "X-Accept-Response-Streaming": "true",
            "X-Accept-Content-Transfer-Encoding": "binary",
            "Referer": f"https://{self._environment.host}/",
            "Origin": f"https://{self._environment.host}",
        }

    def _get_camera_headers(self) -> dict[str, str]:
        """Get headers for camera API requests."""
        headers = {
            "User-Agent": _USER_AGENT,
            "Referer": f"https://{self._environment.host}/",
            "Origin": f"https://{self._environment.host}",
        }
        if self._camera_session_token:  # Legacy account
            cookie = (
                f"{self._environment.camera_cookie_name}{self._camera_session_token}"
            )
            headers["Cookie"] = cookie
        elif self._nest_session:  # Google account
            headers["Authorization"] = f"Basic {self._nest_session.access_token}"
        else:
            raise NotAuthenticatedException("No session for camera command.")
        return headers

    async def _async_set_camera_property(
        self, device: NestCamera, key: str, value: bool
    ) -> None:
        """Set properties for a camera via the dropcams API."""
        key_map = {
            "streaming_enabled": "streaming.enabled",
            "audio_enabled": "audio.enabled",
            "indoor_chime_enabled": "doorbell.indoor_chime.enabled",
            "doorbell_chime_assist_enabled": "doorbell.chime_assist.enabled",
            "irled_enabled": "irled.state",
            "status_led_enabled": "statusled.brightness",
            "video_flipped": "video.flipped",
        }
        api_key = key_map.get(key)
        if not api_key:
            raise PynestException(f"Unsupported camera property: {key}")

        # Handle special value mapping for some properties
        api_value = str(value).lower()
        if key == "irled_enabled":
            api_value = "auto_on" if value else "always_off"
        elif key == "status_led_enabled":
            # 0=auto, 1=low, 2=high. We map enabled to "auto" (0).
            api_value = "0" if value else "1"

        camera_uuid = device.object_key.split(".")[1]
        payload = {"uuid": camera_uuid, api_key: api_value}
        url = f"https://webapi.{self._environment.camera_host}/api/dropcams.set_properties"
        _LOGGER.debug(
            "Setting camera property via URL %s with payload: %s", url, payload
        )

        headers = self._get_camera_headers()

        async def _do_post():
            async with self._session.post(
                url, headers=headers, data=payload
            ) as response:
                if response.status in (401, 403):
                    raise NotAuthenticatedException(
                        f"Authentication failed: {response.status}"
                    )
                if not response.ok:
                    raise PynestException(
                        f"Error setting camera property: {await response.text()}"
                    )
                result = await response.json()
                if result.get("status") != 0:
                    raise PynestException(
                        f"API error setting camera property: {result}"
                    )

        for attempt in range(3):
            try:
                await _do_post()
            except (ClientError, TimeoutError, PynestException) as err:
                if isinstance(err, NotAuthenticatedException) or attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
            else:
                return

    async def _async_set_protobuf_camera_property(
        self,
        device: NestCamera,
        key: str,
        value: bool,
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a protobuf-enabled Camera."""
        _LOGGER.debug(
            "Setting protobuf camera property for %s: %s=%s",
            device.object_key,
            key,
            value,
        )

        if key == "streaming_enabled":
            # Set Recording Toggle
            target_state = (
                nest_camera_pb2.CameraState.CAMERA_ON
                if value
                else nest_camera_pb2.CameraState.CAMERA_OFF
            )
            now = Timestamp()
            now.GetCurrentTime()

            recording_toggle_settings_trait = _get_trait_copy(
                current_traits, nest_camera_pb2.RecordingToggleSettingsTrait
            )
            recording_toggle_settings_trait.targetCameraState = target_state
            recording_toggle_settings_trait.changeModeReason = 2
            recording_toggle_settings_trait.settingsUpdated.CopyFrom(now)

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                recording_toggle_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="recording_toggle_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

        elif key == "indoor_chime_enabled":
            # Set Doorbell Chime
            doorbell_indoor_chime_settings_trait = _get_trait_copy(
                current_traits, nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait
            )
            doorbell_indoor_chime_settings_trait.chimeEnabled = value

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                doorbell_indoor_chime_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="doorbell_indoor_chime_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

        elif key == "audio_enabled":
            # Set Microphone
            microphone_settings_trait = _get_trait_copy(
                current_traits, nest_audio_pb2.MicrophoneSettingsTrait
            )
            microphone_settings_trait.enableMicrophone = value

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                microphone_settings_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="microphone_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

    async def _async_set_protobuf_protect_property(
        self,
        device: NestProtect,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a protobuf-enabled Nest Protect."""
        _LOGGER.debug(
            "Setting protobuf protect property for %s: %s", device.object_key, data
        )

        if "ntp_green_led_enable" in data:
            nighttime_promise_settings_trait = _get_trait_copy(
                current_traits, nest_protect_pb2.NightTimePromiseSettingsTrait
            )
            nighttime_promise_settings_trait.greenLedEnabled = data[
                "ntp_green_led_enable"
            ]

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                nighttime_promise_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="night_time_promise_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

        # These must be sent together to avoid overwriting the other with False
        if "heads_up_enable" in data or "steam_detection_enable" in data:
            safety_alarm_settings_trait = _get_trait_copy(
                current_traits, nest_safety_pb2.SafetyAlarmSettingsTrait
            )

            if "heads_up_enable" in data:
                safety_alarm_settings_trait.headsUpEnabled = data["heads_up_enable"]
            if "steam_detection_enable" in data:
                safety_alarm_settings_trait.steamDetectionEnabled = data[
                    "steam_detection_enable"
                ]

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                safety_alarm_settings_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="safety_alarm_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

        # Handles both Enable (via triggers) and Brightness (via brightnessDiscrete)
        # Updates are merged so changing one preserves the other.
        if "night_light_enable" in data or "night_light_brightness" in data:
            # We must use cached trait state to correctly set both fields
            enhanced_pathlight_settings_trait = _get_trait_copy(
                current_traits, nest_ui_pb2.EnhancedPathlightSettingsTrait
            )

            # --- Brightness Logic ---
            # If brightness is provided in update, use it. Otherwise, rely on existing trait value.
            if "night_light_brightness" in data:
                target_brightness = data["night_light_brightness"]
                brightness_enum = nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_BRIGHTNESS_DISCRETE_LOW
                if target_brightness == 2:
                    brightness_enum = nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_BRIGHTNESS_DISCRETE_MEDIUM
                elif target_brightness == 3:
                    brightness_enum = nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_BRIGHTNESS_DISCRETE_HIGH
                enhanced_pathlight_settings_trait.brightnessDiscrete = brightness_enum

            # --- Enable/Trigger Logic ---
            if "night_light_enable" in data:
                target_enable = data["night_light_enable"]
                if target_enable:
                    # To enable, we set triggers. We start by clearing any existing.
                    enhanced_pathlight_settings_trait.triggers.clear()

                    # Standard Trigger (Darkness + Motion + 10m Timeout)
                    t1 = nest_ui_pb2.EnhancedPathlightSettingsTrait.PathlightTrigger(
                        activationConditions=[
                            nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_CONDITION_DARKNESS,
                            nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_CONDITION_MOTION,
                        ],
                        timeout=Duration(seconds=600),
                    )
                    # triggers is a map so there is no IndexError
                    enhanced_pathlight_settings_trait.triggers[1].CopyFrom(t1)

                    # Wired Trigger (Darkness + Motion + Line Power)
                    # Use device property to check if wired
                    if getattr(device, "line_power_present", False):
                        t0 = nest_ui_pb2.EnhancedPathlightSettingsTrait.PathlightTrigger(
                            activationConditions=[
                                nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_CONDITION_DARKNESS,
                                nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_CONDITION_MOTION,
                                nest_ui_pb2.EnhancedPathlightSettingsTrait.PATHLIGHT_CONDITION_LINE_POWER,
                            ]
                        )
                        enhanced_pathlight_settings_trait.triggers[0].CopyFrom(t0)
                else:
                    # To disable, clear triggers
                    enhanced_pathlight_settings_trait.triggers.clear()

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                enhanced_pathlight_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="pathlight_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

    async def _async_send_command(
        self, device: NestDevice, command: v1_pb2.ResourceCommand
    ) -> v1_pb2.SendCommandResponse:
        """Send a command via the protobuf API."""
        send_command_req = v1_pb2.SendCommandRequest(
            resourceRequest=v1_pb2.ResourceRequest(
                resourceId=device.object_key, requestId=str(uuid.uuid4())
            ),
            resourceCommands=[command],
        )

        url = f"https://{self._environment.grpc_host}{_SEND_COMMAND_ENDPOINT}"

        async def _do_send():
            async with self._session.post(
                url,
                data=send_command_req.SerializeToString(),
                headers=self._get_protobuf_headers(),
                timeout=ClientTimeout(total=_PROTOBUF_COMMAND_TIMEOUT),
            ) as response:
                if response.status in (401, 403):
                    raise NotAuthenticatedException(
                        f"Authentication failed: {response.status}"
                    )
                if not response.ok:
                    raise PynestException(
                        f"Error sending command: {await response.text()}"
                    )

                response_bytes = await response.read()
                send_command_resp = v1_pb2.SendCommandResponse()
                send_command_resp.ParseFromString(response_bytes)
                _LOGGER.debug("SendCommand response: %s", send_command_resp)
                if send_command_resp.status.code != 0:
                    status_code = send_command_resp.status.code
                    msg = f"Command failed with code {status_code}: {send_command_resp.status.message}"
                    if status_code == 16:
                        raise NotAuthenticatedException(msg)
                    if status_code in _NON_RETRYABLE_CODES:
                        raise NonRetryablePynestException(msg)
                    raise PynestException(msg)
                return send_command_resp

        for attempt in range(3):
            try:
                return await _do_send()
            except (ClientError, TimeoutError, PynestException) as err:
                if (
                    isinstance(
                        err, (NotAuthenticatedException, NonRetryablePynestException)
                    )
                    or attempt == 2
                ):
                    raise
                await asyncio.sleep(0.5 * (2**attempt))

        # This should be unreachable due to the raise in the last retry attempt.
        raise PynestException("Command failed after all retry attempts")

    async def _async_update_trait_state(
        self, trait_update_request: v1_pb2.TraitUpdateStateRequest
    ) -> None:
        """Update a device's trait state via the protobuf API."""
        batch_update_req = v1_pb2.BatchUpdateStateRequest(
            batchUpdateStateRequest=[trait_update_request]
        )
        _LOGGER.debug("BatchUpdate request: %s", batch_update_req)
        url = f"https://{self._environment.grpc_host}{_BATCH_UPDATE_ENDPOINT}"

        async def _do_update():
            async with self._session.post(
                url,
                data=batch_update_req.SerializeToString(),
                headers=self._get_protobuf_headers(),
                timeout=ClientTimeout(total=_PROTOBUF_COMMAND_TIMEOUT),
            ) as response:
                if response.status in (401, 403):
                    raise NotAuthenticatedException(
                        f"Authentication failed: {response.status}"
                    )
                if not response.ok:
                    raise PynestException(
                        f"Error updating trait state: {await response.text()}"
                    )
                response_bytes = await response.read()
                batch_update_resp = v1_pb2.BatchUpdateStateResponse()
                batch_update_resp.ParseFromString(response_bytes)
                _LOGGER.debug("BatchUpdate response: %s", batch_update_resp)
                if batch_update_resp.status.code != 0:
                    status_code = batch_update_resp.status.code
                    msg = f"Batch command failed with code {status_code}: {batch_update_resp.status.message}"
                    if status_code == 16:
                        raise NotAuthenticatedException(msg)
                    if status_code in _NON_RETRYABLE_CODES:
                        raise NonRetryablePynestException(msg)
                    raise PynestException(msg)

                for resp in batch_update_resp.batchUpdateStateResponse:
                    for op in resp.traitOperations:
                        if op.status.code != 0:
                            status_code = op.status.code
                            msg = f"Trait update failed with code {status_code}: {op.status.message}"
                            if status_code == 16:
                                raise NotAuthenticatedException(msg)
                            if status_code in _NON_RETRYABLE_CODES:
                                raise NonRetryablePynestException(msg)
                            raise PynestException(msg)

        for attempt in range(3):
            try:
                await _do_update()
            except (ClientError, TimeoutError, PynestException) as err:
                if (
                    isinstance(
                        err, (NotAuthenticatedException, NonRetryablePynestException)
                    )
                    or attempt == 2
                ):
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
            else:
                return

    async def _async_set_lock_property(
        self,
        device: NestLock,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a Nest x Yale Lock."""
        if "bolt_locked" in data:
            state = (
                weave_security_pb2.BoltLockTrait.BoltState.BOLT_STATE_EXTENDED
                if data["bolt_locked"]
                else weave_security_pb2.BoltLockTrait.BoltState.BOLT_STATE_RETRACTED
            )

            command = v1_pb2.ResourceCommand(traitLabel="bolt_lock")
            command.command.Pack(
                weave_security_pb2.BoltLockTrait.BoltLockChangeRequest(
                    state=state,
                    boltLockActor=weave_security_pb2.BoltLockTrait.BoltLockActorStruct(
                        method=weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT
                    ),
                ),
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )
            await self._async_send_command(device, command)
        if "auto_relock_duration" in data or "auto_relock_on" in data:
            state_proto = _get_trait_copy(
                current_traits, weave_security_pb2.BoltLockSettingsTrait
            )
            if "auto_relock_on" in data:
                state_proto.autoRelockOn = data["auto_relock_on"]
            if "auto_relock_duration" in data:
                state_proto.autoRelockDuration.seconds = data["auto_relock_duration"]

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(state_proto, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX)

            request = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="bolt_lock_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(request)

    def _update_eco_mode_settings(
        self,
        data: dict[str, Any],
        eco_mode_settings_trait: Any,
    ) -> bool:
        """Update Eco mode trait values from data."""
        if not (
            "target_temperature" in data
            or "target_temperature_low" in data
            or "target_temperature_high" in data
        ):
            return False

        target_val = data.get("target_temperature")
        if target_val is not None:
            if eco_mode_settings_trait.ecoTemperatureHeat.enabled:
                eco_mode_settings_trait.ecoTemperatureHeat.value.value = target_val
            if eco_mode_settings_trait.ecoTemperatureCool.enabled:
                eco_mode_settings_trait.ecoTemperatureCool.value.value = target_val

        if (
            "target_temperature_low" in data
            and eco_mode_settings_trait.ecoTemperatureHeat.enabled
        ):
            eco_mode_settings_trait.ecoTemperatureHeat.value.value = data[
                "target_temperature_low"
            ]
        if (
            "target_temperature_high" in data
            and eco_mode_settings_trait.ecoTemperatureCool.enabled
        ):
            eco_mode_settings_trait.ecoTemperatureCool.value.value = data[
                "target_temperature_high"
            ]
        return True

    def _update_target_temperature_settings(
        self,
        device: NestThermostat,
        data: dict[str, Any],
        target_temperature_settings_trait: Any,
        eco_mode_active: bool,
    ) -> bool:
        """Update Target Temperature trait values from data."""
        update_target = False

        if "hvac_mode" in data:
            update_target = True
            mode = data["hvac_mode"]
            enabled = mode != ThermostatHvacMode.OFF
            target_temperature_settings_trait.enabled.value = enabled
            if enabled:
                if mode == ThermostatHvacMode.HEAT:
                    target_temperature_settings_trait.targetTemperature.setpointType = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_HEAT
                elif mode == ThermostatHvacMode.COOL:
                    target_temperature_settings_trait.targetTemperature.setpointType = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_COOL
                elif mode == ThermostatHvacMode.RANGE:
                    target_temperature_settings_trait.targetTemperature.setpointType = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_RANGE

        if not eco_mode_active and (
            "target_temperature" in data
            or "target_temperature_low" in data
            or "target_temperature_high" in data
        ):
            update_target = True
            self._apply_target_temperature_to_trait(
                device, data, target_temperature_settings_trait
            )

        return update_target

    def _apply_target_temperature_to_trait(
        self,
        device: NestThermostat,
        data: dict[str, Any],
        target_temperature_settings_trait: Any,
    ) -> None:
        """Calculate and apply heating and cooling targets."""
        heating_target = 20.0
        cooling_target = 25.0
        if target_temperature_settings_trait.HasField("targetTemperature"):
            if target_temperature_settings_trait.targetTemperature.HasField(
                "heatingTarget"
            ):
                heating_target = target_temperature_settings_trait.targetTemperature.heatingTarget.value
            if target_temperature_settings_trait.targetTemperature.HasField(
                "coolingTarget"
            ):
                cooling_target = target_temperature_settings_trait.targetTemperature.coolingTarget.value
        else:
            if device.target_temperature_low is not None:
                heating_target = device.target_temperature_low
            elif (
                device.hvac_mode == ThermostatHvacMode.HEAT
                and device.target_temperature is not None
            ):
                heating_target = device.target_temperature

            if device.target_temperature_high is not None:
                cooling_target = device.target_temperature_high
            elif (
                device.hvac_mode == ThermostatHvacMode.COOL
                and device.target_temperature is not None
            ):
                cooling_target = device.target_temperature

        temp_val = data.get("target_temperature")

        # Derive setpointType safely, pulling from device fallback if cache is cold
        if "hvac_mode" in data:
            setpoint_type = (
                target_temperature_settings_trait.targetTemperature.setpointType
            )
        else:
            setpoint_type = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_HEAT
            if device.hvac_mode == ThermostatHvacMode.COOL:
                setpoint_type = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_COOL
            elif (
                device.hvac_mode == ThermostatHvacMode.RANGE
                or "target_temperature_low" in data
                or "target_temperature_high" in data
            ):
                setpoint_type = nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_RANGE
            target_temperature_settings_trait.targetTemperature.setpointType = (
                setpoint_type
            )

        if (
            setpoint_type
            == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_HEAT
            and temp_val is not None
        ):
            heating_target = temp_val
        elif (
            setpoint_type
            == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_COOL
            and temp_val is not None
        ):
            cooling_target = temp_val
        elif (
            setpoint_type
            == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_RANGE
        ):
            if "target_temperature_low" in data:
                heating_target = data["target_temperature_low"]
            if "target_temperature_high" in data:
                cooling_target = data["target_temperature_high"]

        target_temperature_settings_trait.targetTemperature.heatingTarget.value = (
            heating_target
        )
        target_temperature_settings_trait.targetTemperature.coolingTarget.value = (
            cooling_target
        )

    async def _set_proto_thermostat_target_settings(
        self,
        device: NestThermostat,
        data: dict[str, Any],
        now: Timestamp,
        current_traits: dict[str, Any] | None = None,
        is_eco: bool | None = None,
    ) -> None:
        """Handle combined temperature and HVAC mode updates for protobuf thermostat."""
        if is_eco is None:
            is_eco = device.is_eco_mode

        eco_mode_active = (
            device.hvac_mode
            in (ThermostatHvacMode.OFF, "eco", "ecoheat", "ecocool", "ecorange")
            or is_eco
        )

        update_eco = False
        eco_mode_settings_trait = _get_trait_copy(
            current_traits, nest_hvac_pb2.EcoModeSettingsTrait
        )
        if eco_mode_active:
            update_eco = self._update_eco_mode_settings(data, eco_mode_settings_trait)

        target_temperature_settings_trait = _get_trait_copy(
            current_traits, nest_hvac_pb2.TargetTemperatureSettingsTrait
        )
        update_target = self._update_target_temperature_settings(
            device, data, target_temperature_settings_trait, eco_mode_active
        )

        # Execute updates sequentially (but properly combined traits)
        if update_eco:
            any_proto_eco = google.protobuf.any_pb2.Any()
            any_proto_eco.Pack(
                eco_mode_settings_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX
            )
            req_eco = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="eco_mode_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto_eco,
            )
            await self._async_update_trait_state(req_eco)

        if update_target:
            actor_info = nest_hvac_pb2.HvacActor.HvacActorStruct(
                method=nest_hvac_pb2.HvacActor.HvacActorMethod.HVAC_ACTOR_METHOD_IOS,
                originator=weave_common_pb2.ResourceId(resourceId=device.object_key),
                timeOfAction=now,
            )
            target_temperature_settings_trait.targetTemperature.currentActorInfo.CopyFrom(
                actor_info
            )

            any_proto_target = google.protobuf.any_pb2.Any()
            any_proto_target.Pack(
                target_temperature_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )
            req_target = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="target_temperature_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto_target,
            )
            await self._async_update_trait_state(req_target)

    async def _set_proto_thermostat_fan(
        self,
        device: NestThermostat,
        data: dict[str, Any],
        now: Timestamp,
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Handle fan updates for protobuf thermostat."""
        # Determine if fan should be on
        timeout_end = data.get("fan_timer_timeout", 0)
        is_on = timeout_end > time.time()

        speed_str = data.get(
            "fan_timer_speed", f"stage{device.fan_timer_speed}"
        )  # e.g. "stage1"
        speed_val = 1
        if speed_str.startswith("stage"):
            with contextlib.suppress(ValueError):
                speed_val = int(speed_str.replace("stage", ""))

        speed_enum = (
            nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE1
        )
        if speed_val == 2:
            speed_enum = (
                nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE2
            )
        elif speed_val == 3:
            speed_enum = (
                nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE3
            )

        timer_end_ts = Timestamp()
        if is_on:
            timer_end_ts.FromSeconds(timeout_end)
        else:
            timer_end_ts.FromSeconds(0)

        fan_control_settings_trait = _get_trait_copy(
            current_traits, nest_hvac_pb2.FanControlSettingsTrait
        )
        fan_control_settings_trait.timerEnd.CopyFrom(timer_end_ts)
        fan_control_settings_trait.timerSpeed = speed_enum

        any_proto = google.protobuf.any_pb2.Any()
        any_proto.Pack(
            fan_control_settings_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX
        )

        req = v1_pb2.TraitUpdateStateRequest(
            traitRequest=v1_pb2.TraitRequest(
                resourceId=device.object_key,
                traitLabel="fan_control_settings",
                requestId=str(uuid.uuid4()),
            ),
            state=any_proto,
        )
        await self._async_update_trait_state(req)

    async def _async_set_protobuf_thermostat_property(
        self,
        device: NestThermostat,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set properties for a protobuf-enabled Nest Thermostat."""
        _LOGGER.debug(
            "Setting protobuf thermostat property for %s: %s", device.object_key, data
        )

        now = Timestamp()
        now.GetCurrentTime()

        # Compute the intended eco state from the payload upfront, before any
        # API calls, so that later
        # steps in this function use the correct intended state rather than the
        # stale coordinator snapshot (which won't update until the next observe).
        eco_data = data.get("eco", {})
        preset_val = data.get("preset_mode") or eco_data.get("mode")
        if data.get("exit_eco"):
            # Semantic flag from ClimateEntity: exit eco before applying a new setpoint
            intended_is_eco = False
            preset_val = "schedule"  # Ensures the eco-off command block below fires
        elif preset_val:
            intended_is_eco = preset_val in ("manual-eco", "eco")
        else:
            intended_is_eco = device.is_eco_mode

        # Handle Eco Mode (Preset) FIRST
        # sending eco-off before the temperature change, so the backend
        # processes the mode transition before applying the new setpoint.
        if preset_val:
            mode_enum = (
                nest_hvac_pb2.EcoModeStateTrait.EcoMode.ECO_MODE_MANUAL_ECO
                if intended_is_eco
                else nest_hvac_pb2.EcoModeStateTrait.EcoMode.ECO_MODE_INACTIVE
            )

            cmd = v1_pb2.ResourceCommand(traitLabel="eco_mode")
            cmd.command.Pack(
                nest_hvac_pb2.EcoModeStateTrait.EcoModeChangeRequest(
                    ecoMode=mode_enum, setAll=False
                ),
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )
            await self._async_send_command(device, cmd)

        # Handle HVAC Mode and Temperature together to prevent race condition overwriting trait states
        if (
            "hvac_mode" in data
            or "target_temperature" in data
            or "target_temperature_low" in data
            or "target_temperature_high" in data
        ):
            await self._set_proto_thermostat_target_settings(
                device, data, now, current_traits, is_eco=intended_is_eco
            )

        # Handle Humidifier, Dehumidifier and Target Humidity
        if (
            "dehumidifier_state" in data
            or "humidifier_state" in data
            or "target_humidity" in data
        ):
            humidity_control_settings_trait = _get_trait_copy(
                current_traits, nest_hvac_pb2.HumidityControlSettingsTrait
            )
            if "dehumidifier_state" in data:
                humidity_control_settings_trait.dehumidifierTargetHumidity.enabled = (
                    data["dehumidifier_state"]
                )
            if "humidifier_state" in data:
                humidity_control_settings_trait.humidifierTargetHumidity.enabled = data[
                    "humidifier_state"
                ]
            if "target_humidity" in data:
                humidity_level = float(data["target_humidity"])
                humidity_control_settings_trait.targetHumidity.value = humidity_level
                humidity_control_settings_trait.dehumidifierTargetHumidity.value = (
                    humidity_level
                )
                humidity_control_settings_trait.humidifierTargetHumidity.value = (
                    humidity_level
                )

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                humidity_control_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="humidity_control_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

        # Handle Fan Control
        if "fan_timer_timeout" in data or "fan_timer_speed" in data:
            await self._set_proto_thermostat_fan(device, data, now, current_traits)

        # Handle Temperature Lock
        if "temperature_lock" in data:
            temperature_lock_settings_trait = _get_trait_copy(
                current_traits, nest_hvac_pb2.TemperatureLockSettingsTrait
            )
            temperature_lock_settings_trait.enabled = data["temperature_lock"]

            any_proto = google.protobuf.any_pb2.Any()
            any_proto.Pack(
                temperature_lock_settings_trait,
                type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
            )

            req = v1_pb2.TraitUpdateStateRequest(
                traitRequest=v1_pb2.TraitRequest(
                    resourceId=device.object_key,
                    traitLabel="temperature_lock_settings",
                    requestId=str(uuid.uuid4()),
                ),
                state=any_proto,
            )
            await self._async_update_trait_state(req)

    async def async_set_device_data(
        self,
        device: NestDevice,
        data: dict[str, Any],
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set device data, dispatching to the correct internal method."""
        if isinstance(device, NestCamera):
            if device.is_protobuf:
                for key, value in data.items():
                    await self._async_set_protobuf_camera_property(
                        device, key, value, current_traits
                    )
            else:
                for key, value in data.items():
                    await self._async_set_camera_property(device, key, value)
        elif isinstance(device, NestHeatLink):
            await self._async_set_heatlink_property(device, data, current_traits)
        elif isinstance(device, NestThermostat):
            if device.is_protobuf:
                await self._async_set_protobuf_thermostat_property(
                    device, data, current_traits
                )
            else:
                await self._async_set_thermostat_property(device.object_key, data)
        elif isinstance(device, NestStructure):
            await self._async_set_structure_property(device, data)
        elif isinstance(device, NestLock):
            await self._async_set_lock_property(device, data, current_traits)
        elif isinstance(device, NestProtect):
            if device.is_protobuf:
                await self._async_set_protobuf_protect_property(
                    device, data, current_traits
                )
            else:
                await self._async_set_generic_property(device.object_key, data)
        elif isinstance(device, NestTempSensor):
            if "is_active_sensor" in data:
                await self._async_set_sensor_active(
                    device, data["is_active_sensor"], current_traits
                )
            else:
                await self._async_set_generic_property(device.object_key, data)
        else:
            await self._async_set_generic_property(device.object_key, data)

    async def _async_set_sensor_active(
        self,
        device: NestTempSensor,
        active: bool,
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set a temperature sensor as the active sensor for its thermostat."""
        if not device.associated_thermostat_object_key:
            _LOGGER.warning(
                "Sensor %s is not associated with any thermostat", device.name
            )
            return

        if device.is_protobuf:
            await self._async_set_protobuf_sensor_active(device, active, current_traits)
        else:
            await self._async_set_legacy_sensor_active(device, active)

    async def _async_set_protobuf_sensor_active(
        self,
        device: NestTempSensor,
        active: bool,
        current_traits: dict[str, Any] | None = None,
    ) -> None:
        """Set active sensor via Protobuf."""
        # We need the current RCS trait to ensure we don't wipe other settings
        # The RCS trait lives on the Thermostat (associated_thermostat_object_key)
        thermostat_key = device.associated_thermostat_object_key
        if not thermostat_key:
            _LOGGER.warning(
                "Sensor %s is not associated with any thermostat", device.name
            )
            return

        rcs_trait = _get_trait_copy(
            current_traits, nest_hvac_pb2.RemoteComfortSensingSettingsTrait
        )
        RcsSourceType = nest_hvac_pb2.RemoteComfortSensingSettingsTrait.RcsSourceType

        if active:
            # Switch to Single Sensor mode using this sensor ID
            rcs_trait.activeRcsSelection.rcsSourceType = (
                RcsSourceType.RCS_SOURCE_TYPE_SINGLE_SENSOR
            )
            rcs_trait.activeRcsSelection.activeRcsSensor.resourceId = device.object_key
        elif (
            rcs_trait.activeRcsSelection.rcsSourceType
            == RcsSourceType.RCS_SOURCE_TYPE_SINGLE_SENSOR
            and rcs_trait.activeRcsSelection.activeRcsSensor.resourceId
            == device.object_key
        ):
            # Only switch back to backplate if THIS sensor is currently the active one
            rcs_trait.activeRcsSelection.rcsSourceType = (
                RcsSourceType.RCS_SOURCE_TYPE_BACKPLATE
            )
            rcs_trait.activeRcsSelection.ClearField("activeRcsSensor")
        else:
            return  # No change needed

        any_proto = google.protobuf.any_pb2.Any()
        any_proto.Pack(rcs_trait, type_url_prefix=_NESTLABS_TYPE_URL_PREFIX)

        req = v1_pb2.TraitUpdateStateRequest(
            traitRequest=v1_pb2.TraitRequest(
                resourceId=thermostat_key,
                traitLabel="remote_comfort_sensing_settings",
                requestId=str(uuid.uuid4()),
            ),
            state=any_proto,
        )
        await self._async_update_trait_state(req)

    async def _async_set_legacy_sensor_active(
        self, device: NestTempSensor, active: bool
    ) -> None:
        """Set active sensor via Legacy API."""
        # For legacy, the key is usually device.<serial>, but rcs_settings uses the serial directly
        # rcs_settings.<serial>
        thermostat_key = device.associated_thermostat_object_key
        if not thermostat_key:
            _LOGGER.warning(
                "Sensor %s is not associated with any thermostat", device.name
            )
            return
        device_id = thermostat_key.split(".")[1]
        rcs_key = f"rcs_settings.{device_id}"

        if active:
            payload = {
                "active_rcs_sensors": [device.object_key],
                "rcs_control_setting": "OVERRIDE",
            }
        else:
            payload = {"active_rcs_sensors": [], "rcs_control_setting": "OFF"}

        await self._async_set_generic_property(rcs_key, payload)

    async def async_get_camera_snapshot(self, device: NestCamera) -> bytes | None:
        """Get a snapshot from a camera."""
        if not device.nexus_api_http_server_url:
            _LOGGER.error(
                "Cannot get snapshot for %s, nexus_api_http_server_url is missing",
                device.object_key,
            )
            return None

        if device.is_protobuf:
            try:
                upload_req = (
                    nest_camera_pb2.UploadLiveImageTrait.UploadLiveImageRequest()
                )
                command = v1_pb2.ResourceCommand(traitLabel="upload_live_image")
                command.command.Pack(
                    upload_req,
                    type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
                )
                await self._async_send_command(device, command)
            except PynestException as err:
                _LOGGER.warning("Failed to send upload_live_image command: %r", err)
            url = device.nexus_api_http_server_url
        else:
            camera_uuid = device.object_key.split(".")[1]
            url = urljoin(
                device.nexus_api_http_server_url,
                f"/get_image?uuid={camera_uuid}",
            )
        _LOGGER.debug("Requesting camera snapshot from URL: %s", url)

        async with self._session.get(
            url, headers=self._get_camera_headers()
        ) as response:
            if response.ok:
                return await response.read()
            _LOGGER.error(
                "Failed to get camera snapshot. Status: %s, URL: %s",
                response.status,
                response.url,
            )
            return None

    @contextlib.asynccontextmanager
    async def async_get_camera_event_media_stream(
        self,
        device: NestCamera,
        event_id: str,
        height: int | None = None,
        format: str = "mp4",
    ):
        """Get a historical media stream from a camera event."""
        if device.is_protobuf:
            # Historical MP4 clips are not available over simple REST GET for Protobuf cameras
            yield None
            return

        if not device.nexus_api_http_server_url:
            _LOGGER.error(
                "Cannot get event clip for %s, nexus_api_http_server_url is missing",
                device.object_key,
            )
            yield None
            return

        camera_uuid = device.object_key.split(".")[1]
        params: dict[str, str | int] = {
            "uuid": camera_uuid,
            "cuepoint_id": event_id,
            "format": format,
        }
        if height:
            params["height"] = height

        url = urljoin(device.nexus_api_http_server_url, "/get_event_clip")
        _LOGGER.debug("Requesting event clip from URL: %s with params %s", url, params)

        async with self._session.get(
            url, params=params, headers=self._get_camera_headers()
        ) as response:
            if response.ok:
                yield response
            else:
                _LOGGER.error(
                    "Failed to get camera event clip. Status: %s, URL: %s",
                    response.status,
                    response.url,
                )
                yield None

    def _parse_protobuf_camera_event(
        self, cam_event: Any, EventTypeEnum: Any, events: list[dict[str, Any]]
    ) -> None:
        """Parse a single protobuf camera event."""
        event_types = []
        for t in cam_event.eventType:
            try:
                t_str = EventTypeEnum.Name(t)
                # Map Protobuf enums to legacy API string formats
                if t_str == "EVENT_UNFAMILIAR_FACE":
                    event_types.append("unfamiliar-face")
                elif t_str == "EVENT_PERSON_TALKING":
                    event_types.append("personHeard")
                elif t_str == "EVENT_DOG_BARKING":
                    event_types.append("dogBarking")
                elif t_str.startswith("EVENT_"):
                    event_types.append(t_str[6:].lower())
                else:
                    event_types.append(t_str.lower())
            except ValueError:
                continue

        if not event_types:
            return

        # Convert Timestamp to float seconds
        start_t = cam_event.startTime.seconds + (cam_event.startTime.nanos / 1e9)
        end_t = cam_event.endTime.seconds + (cam_event.endTime.nanos / 1e9)

        # Map zone indices
        zone_ids = [
            z.zoneIndex for z in cam_event.activityZone if z.zoneIndex is not None
        ]
        # If generic motion without specific zone, default to zone 1
        if not zone_ids:
            zone_ids = [1]

        events.append(
            {
                "id": cam_event.eventId,
                "start_time": start_t,
                "end_time": end_t,
                "types": event_types,
                "zone_ids": zone_ids,
            }
        )

    async def _async_get_protobuf_camera_events(
        self,
        device: NestCamera,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get camera events via Protobuf API."""
        if start_time is None:
            start_time = int(time.time() - 60)
        if end_time is None:
            end_time = int(time.time())

        # Construct Request
        start_ts = Timestamp()
        start_ts.FromSeconds(start_time)
        end_ts = Timestamp()
        end_ts.FromSeconds(end_time)

        history_req = nest_history_pb2.CameraObservationHistoryTrait.CameraObservationHistoryRequest(
            queryStartTime=start_ts,
            queryEndTime=end_ts,
        )

        command = v1_pb2.ResourceCommand(traitLabel="camera_observation_history")
        command.command.Pack(
            history_req,
            type_url_prefix=_NESTLABS_TYPE_URL_PREFIX,
        )

        try:
            resp = await self._async_send_command(device, command)
        except PynestException as err:
            _LOGGER.warning("Failed to fetch protobuf camera events: %r", err)
            return []

        events: list[dict[str, Any]] = []

        # Aliases for readability based on history_pb2 structure
        HistoryTrait = nest_history_pb2.CameraObservationHistoryTrait
        ResponseClass = HistoryTrait.CameraObservationHistoryResponse
        # EventType is defined inside CameraEventTimeWindow
        EventTypeEnum = ResponseClass.CameraEventTimeWindow.EventType

        # Parse Response
        # Structure: SendCommandResponse -> TraitOperation -> Event (Any) -> CameraObservationHistoryResponse
        for trait_op in resp.sendCommandResponse:
            for op in trait_op.traitOperations:
                if not op.HasField("event") or not op.event.HasField("event"):
                    continue

                # Unpack the inner event
                if not op.event.event.Is(ResponseClass.DESCRIPTOR):
                    continue

                history_response = ResponseClass()
                op.event.event.Unpack(history_response)

                if not history_response.HasField("cameraEventWindow"):
                    continue

                # Iterate through events in the time window
                for cam_event in history_response.cameraEventWindow.cameraEvent:
                    self._parse_protobuf_camera_event(cam_event, EventTypeEnum, events)

        # Sort by start_time descending to match legacy API behavior
        events.sort(key=lambda x: x["start_time"], reverse=True)
        return events

    async def async_get_camera_events(
        self,
        device: NestCamera,
        start_time: int | None = None,
        end_time: int | None = None,
        types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get camera events from the cuepoint API."""
        if device.is_protobuf:
            # Protobuf camera events fail with:
            # "Command failed with code 7: Client is not authorized to access traits"
            # on legacy non-Google accounts.
            if self._camera_session_token is not None:
                if not self._legacy_protobuf_events_warned:
                    _LOGGER.warning(
                        "Protobuf camera events are not supported for legacy Nest accounts"
                    )
                    self._legacy_protobuf_events_warned = True
                return []
            return await self._async_get_protobuf_camera_events(
                device, start_time, end_time
            )

        if not device.nexus_api_http_server_url:
            return []

        if start_time is None:
            start_time = int(time.time() - 60)

        camera_uuid = device.object_key.split(".")[1]
        url = f"{device.nexus_api_http_server_url}/cuepoint/{camera_uuid}/2"
        params: dict[str, Any] = {"start_time": start_time}
        if end_time:
            params["end_time"] = end_time
        if types:
            params["types"] = ",".join(types)

        if end_time:
            _LOGGER.debug(
                "Requesting camera events from URL: %s with params %s", url, params
            )
        async with self._session.get(
            url,
            params=params,
            headers=self._get_camera_headers(),
        ) as response:
            if not response.ok:
                _LOGGER.warning(
                    "Failed to fetch camera events: %s, URL: %s",
                    response.status,
                    response.url,
                )
                return []
            return await response.json()

    async def async_get_camera_properties(self, device: NestCamera) -> dict[str, Any]:
        """Get camera properties from the API."""
        # Protobuf devices update properties via traits, and don't use the legacy quartz key format
        if device.is_protobuf or not device.object_key.startswith("quartz."):
            return {}

        camera_uuid = device.object_key.split(".")[1]
        url = f"https://webapi.{self._environment.camera_host}/api/cameras.get_with_properties"
        params = {"uuid": camera_uuid}
        _LOGGER.debug(
            "Requesting camera properties from URL: %s with params %s", url, params
        )
        async with self._session.get(
            url, params=params, headers=self._get_camera_headers()
        ) as response:
            if not response.ok:
                _LOGGER.warning(
                    "Failed to fetch camera properties: %s, URL: %s",
                    response.status,
                    response.url,
                )
                return {}
            data = await response.json()
            try:
                return data["items"][0].get("properties", {})
            except KeyError, IndexError:
                return {}

    def _parse_observe_buffer(self, buffer: bytearray):
        """Parse the observe buffer to extract responses."""
        while True:
            if not buffer:
                break

            tag, tag_size = _decode_varint(buffer)
            if tag is None:
                break

            wire_type = tag & 0x07
            if wire_type != 2:
                _LOGGER.debug(
                    "Unexpected wire type %s in observe stream, resetting buffer",
                    wire_type,
                )
                buffer.clear()
                break

            message_length, varint_size = _decode_varint(buffer[tag_size:])
            if message_length is None:
                break

            frame_size = tag_size + varint_size + message_length
            if len(buffer) < frame_size:
                break

            full_frame_data = buffer[:frame_size]
            del buffer[:frame_size]

            if tag >> 3 == 1:  # Field 1: observeResponse
                outer_response = v2_pb2.ObserveResponse()
                outer_response.ParseFromString(bytes(full_frame_data))

                for inner_response in outer_response.observeResponse:
                    updates = self._parse_observe_response(inner_response)
                    if updates:
                        yield updates
            else:
                _LOGGER.debug(
                    "Skipping unknown field tag %s in observe stream",
                    tag >> 3,
                )

    async def async_observe_for_updates(self):
        """Listen for protobuf data updates."""
        url = f"https://{self._environment.grpc_host}{_OBSERVE_ENDPOINT}"
        headers = self._get_protobuf_headers()

        observe_req = v2_pb2.ObserveRequest(
            stateTypes=[v2_pb2.ACCEPTED, v2_pb2.CONFIRMED],
            traitTypeParams=[
                v2_pb2.TraitTypeObserveParams(traitType=trait.DESCRIPTOR.full_name)
                for trait in self._observe_traits
            ],
        )
        request_payload_bytes = observe_req.SerializeToString()

        try:
            async with self._session.post(
                url,
                headers=headers,
                data=request_payload_bytes,
                timeout=ClientTimeout(total=_OBSERVE_TIMEOUT, connect=_CONNECT_TIMEOUT),
            ) as response:
                response.raise_for_status()
                buffer = bytearray()

                while True:
                    chunk = await response.content.read(4096)
                    if not chunk:
                        _LOGGER.debug("Observe stream finished")
                        break
                    buffer.extend(chunk)

                    for updates in self._parse_observe_buffer(buffer):
                        yield updates

        except TimeoutError:
            _LOGGER.debug("Stream connection timed out due to inactivity")
        except ClientError as err:
            if hasattr(err, "status") and err.status in (401, 403):
                raise NotAuthenticatedException(
                    f"Observer auth failed: {err.status}"
                ) from err
            _LOGGER.debug("Observe stream connection error: %s", err)
            raise PynestException(f"Observe stream failed: {err}") from err
        except OSError as err:
            _LOGGER.debug("Observe stream connection error: %s", err)
            raise PynestException(f"Observe stream failed: {err}") from err
        except Exception as err:
            _LOGGER.exception("Observe stream failed")
            raise PynestException(f"Observe stream failed: {err}") from err

    def _parse_observe_response(
        self, inner_response: v2_pb2.ObserveResponse.ObserveResponse
    ) -> dict[str, dict[str, Any]]:
        """Parse a single observe response message."""
        updates: dict[str, dict[str, Any]] = {}

        # Pass 1: Check for label collisions
        self._check_trait_label_collisions(inner_response)

        # Capture resource metadata (type) for device model identification
        for meta in inner_response.resourceMetas:
            self._resource_types[meta.resourceId] = meta.type

        # Pass 2: Parse individual trait states
        for state in inner_response.traitStates:
            type_url = state.patch.values.type_url
            descriptor_full_name = type_url.removeprefix(_NESTLABS_TYPE_URL_PREFIX)
            target_class = _TRAIT_TYPE_TO_CLASS_MAP.get(descriptor_full_name)
            if not target_class:
                _LOGGER.debug("Unknown type_url received, skipping: %s", type_url)
                continue

            unpacked_message = target_class()
            state.patch.values.Unpack(unpacked_message)

            resource_id = state.traitId.resourceId
            trait_label = state.traitId.traitLabel

            _LOGGER.debug(
                "OBSERVE TRAIT MAPPING: resource_id=%s, type_url=%s, trait_label='%s', state_types=%s",
                resource_id,
                type_url,
                trait_label,
                [v2_pb2.StateType.Name(t) for t in state.stateTypes],
            )

            if trait_label.endswith("_bucketized"):
                continue

            if resource_id not in updates:
                updates[resource_id] = {}
                if resource_id in self._resource_types:
                    updates[resource_id]["_resource_type"] = self._resource_types[
                        resource_id
                    ]

            # Store by traitLabel for labels that need
            # label-specific access.
            # Prioritize ACCEPTED over CONFIRMED.
            if (
                trait_label
                and trait_label in _LABEL_SPECIFIC_TRAITS
                and not (
                    trait_label in updates[resource_id]
                    and v2_pb2.ACCEPTED not in state.stateTypes
                )
            ):
                updates[resource_id][trait_label] = unpacked_message

            # Prioritize ACCEPTED over CONFIRMED.
            # If we already have data for this trait in this batch,
            # and the current update is NOT ACCEPTED, ignore it.
            if (
                descriptor_full_name in updates[resource_id]
                and v2_pb2.ACCEPTED not in state.stateTypes
            ):
                continue

            updates[resource_id][descriptor_full_name] = unpacked_message

        return updates

    def _check_trait_label_collisions(
        self, inner_response: v2_pb2.ObserveResponse.ObserveResponse
    ) -> None:
        """Log warnings when multiple different labels are used for the same trait type."""
        seen_labels: dict[str, dict[str, tuple[str, Any]]] = {}
        for state in inner_response.traitStates:
            type_url = state.patch.values.type_url
            descriptor_full_name = type_url.removeprefix(_NESTLABS_TYPE_URL_PREFIX)
            resource_id = state.traitId.resourceId
            trait_label = state.traitId.traitLabel

            if trait_label.endswith("_bucketized"):
                continue

            if resource_id not in seen_labels:
                seen_labels[resource_id] = {}

            existing = seen_labels[resource_id].get(descriptor_full_name)
            if existing:
                prev_label, prev_state = existing
                if (
                    prev_label != trait_label
                    and prev_label not in _LABEL_SPECIFIC_TRAITS
                    and trait_label not in _LABEL_SPECIFIC_TRAITS
                ):
                    # Collision! Unpack both to log full details.
                    target_class = _TRAIT_TYPE_TO_CLASS_MAP.get(descriptor_full_name)
                    if target_class:
                        msg1, msg2 = target_class(), target_class()
                        prev_state.patch.values.Unpack(msg1)
                        state.patch.values.Unpack(msg2)
                        _LOGGER.warning(
                            "Multiple traits of type %s on %s "
                            "with different labels "
                            "('%s' and '%s'), only one will "
                            "be used. Consider adding labels "
                            "to _LABEL_SPECIFIC_TRAITS.\n"
                            "Value 1 (%s): %s\n"
                            "Value 2 (%s): %s",
                            descriptor_full_name,
                            resource_id,
                            prev_label,
                            trait_label,
                            prev_label,
                            msg1,
                            trait_label,
                            msg2,
                        )

            seen_labels[resource_id][descriptor_full_name] = (trait_label, state)

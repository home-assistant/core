"""Common code for Withings."""
import asyncio
from dataclasses import dataclass
import datetime
from datetime import timedelta
from enum import Enum, IntEnum
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union, cast

from aiohttp.web import Response
import requests
from withings_api import AbstractWithingsApi
from withings_api.common import (
    AuthFailedException,
    GetSleepSummaryField,
    MeasureGroupAttribs,
    MeasureType,
    MeasureTypes,
    NotifyAppli,
    SleepGetSummaryResponse,
    UnauthorizedException,
    query_measure_groups,
)

from homeassistant.components import webhook
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.webhook import (
    async_unregister as async_unregister_webhook,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_WEBHOOK_ID,
    HTTP_UNAUTHORIZED,
    MASS_KILOGRAMS,
    PERCENTAGE,
    SPEED_METERS_PER_SECOND,
    TIME_SECONDS,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    AUTH_CALLBACK_PATH,
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
    OAuth2Session,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.network import get_url
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt

from . import const
from .const import CONF_CLOUDHOOK_URL, CONF_USE_WEBHOOK, CONFIG_ENTRY_DATA, Measurement

_LOGGER = logging.getLogger(const.LOG_NAMESPACE)
NOT_AUTHENTICATED_ERROR = re.compile(
    f"^{HTTP_UNAUTHORIZED},.*",
    re.IGNORECASE,
)
DATA_UPDATED_SIGNAL = "withings_entity_state_updated"

MeasurementData = Dict[Measurement, Any]


class NotAuthenticatedError(HomeAssistantError):
    """Raise when not authenticated with the service."""


class ServiceError(HomeAssistantError):
    """Raise when the service has an error."""


class UpdateType(Enum):
    """Data update type."""

    POLL = "poll"
    WEBHOOK = "webhook"


@dataclass(frozen=True)
class WithingsAttribute:
    """Immutable class for describing withings sensor data."""

    measurement: Measurement
    measute_type: Enum
    friendly_name: str
    unit_of_measurement: str
    icon: Optional[str]
    platform: str
    enabled_by_default: bool
    update_type: UpdateType


@dataclass(frozen=True)
class WithingsData:
    """Represents value and meta-data from the withings service."""

    attribute: WithingsAttribute
    value: Any


@dataclass(frozen=True)
class WebhookConfig:
    """Config for a webhook."""

    enabled: bool


DISABLED_WEBHOOK_CONFIG = WebhookConfig(enabled=False)


@dataclass(frozen=True)
class EnabledWebhookConfig(WebhookConfig):
    """Enabled webhook config."""

    id: str
    url: str
    is_cloud: bool
    enabled: bool


@dataclass(frozen=True)
class StateData:
    """State data held by data manager for retrieval by entities."""

    unique_id: str
    state: Any


WITHINGS_ATTRIBUTES = [
    WithingsAttribute(
        Measurement.WEIGHT_KG,
        MeasureType.WEIGHT,
        "Weight",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_MASS_KG,
        MeasureType.FAT_MASS_WEIGHT,
        "Fat Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_FREE_MASS_KG,
        MeasureType.FAT_FREE_MASS,
        "Fat Free Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.MUSCLE_MASS_KG,
        MeasureType.MUSCLE_MASS,
        "Muscle Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.BONE_MASS_KG,
        MeasureType.BONE_MASS,
        "Bone Mass",
        MASS_KILOGRAMS,
        "mdi:weight-kilogram",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HEIGHT_M,
        MeasureType.HEIGHT,
        "Height",
        const.UOM_LENGTH_M,
        "mdi:ruler",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.TEMP_C,
        MeasureType.TEMPERATURE,
        "Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.BODY_TEMP_C,
        MeasureType.BODY_TEMPERATURE,
        "Body Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SKIN_TEMP_C,
        MeasureType.SKIN_TEMPERATURE,
        "Skin Temperature",
        const.UOM_TEMP_C,
        "mdi:thermometer",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.FAT_RATIO_PCT,
        MeasureType.FAT_RATIO,
        "Fat Ratio",
        PERCENTAGE,
        None,
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.DIASTOLIC_MMHG,
        MeasureType.DIASTOLIC_BLOOD_PRESSURE,
        "Diastolic Blood Pressure",
        const.UOM_MMHG,
        None,
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SYSTOLIC_MMGH,
        MeasureType.SYSTOLIC_BLOOD_PRESSURE,
        "Systolic Blood Pressure",
        const.UOM_MMHG,
        None,
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HEART_PULSE_BPM,
        MeasureType.HEART_RATE,
        "Heart Pulse",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SPO2_PCT,
        MeasureType.SP02,
        "SP02",
        PERCENTAGE,
        None,
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.HYDRATION,
        MeasureType.HYDRATION,
        "Hydration",
        MASS_KILOGRAMS,
        "mdi:water",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.PWV,
        MeasureType.PULSE_WAVE_VELOCITY,
        "Pulse Wave Velocity",
        SPEED_METERS_PER_SECOND,
        None,
        SENSOR_DOMAIN,
        True,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY,
        GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
        "Breathing disturbances intensity",
        "",
        "",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_DEEP_DURATION_SECONDS,
        GetSleepSummaryField.DEEP_SLEEP_DURATION,
        "Deep sleep",
        TIME_SECONDS,
        "mdi:sleep",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_TOSLEEP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_SLEEP,
        "Time to sleep",
        TIME_SECONDS,
        "mdi:sleep",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.DURATION_TO_WAKEUP,
        "Time to wakeup",
        TIME_SECONDS,
        "mdi:sleep-off",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_AVERAGE,
        GetSleepSummaryField.HR_AVERAGE,
        "Average heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_MAX,
        GetSleepSummaryField.HR_MAX,
        "Maximum heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_HEART_RATE_MIN,
        GetSleepSummaryField.HR_MIN,
        "Minimum heart rate",
        const.UOM_BEATS_PER_MINUTE,
        "mdi:heart-pulse",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_LIGHT_DURATION_SECONDS,
        GetSleepSummaryField.LIGHT_SLEEP_DURATION,
        "Light sleep",
        TIME_SECONDS,
        "mdi:sleep",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_REM_DURATION_SECONDS,
        GetSleepSummaryField.REM_SLEEP_DURATION,
        "REM sleep",
        TIME_SECONDS,
        "mdi:sleep",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE,
        GetSleepSummaryField.RR_AVERAGE,
        "Average respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_MAX,
        GetSleepSummaryField.RR_MAX,
        "Maximum respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_RESPIRATORY_RATE_MIN,
        GetSleepSummaryField.RR_MIN,
        "Minimum respiratory rate",
        const.UOM_BREATHS_PER_MINUTE,
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SCORE,
        GetSleepSummaryField.SLEEP_SCORE,
        "Sleep score",
        "",
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SNORING,
        GetSleepSummaryField.SNORING,
        "Snoring",
        "",
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_SNORING_EPISODE_COUNT,
        GetSleepSummaryField.SNORING_EPISODE_COUNT,
        "Snoring episode count",
        "",
        None,
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_WAKEUP_COUNT,
        GetSleepSummaryField.WAKEUP_COUNT,
        "Wakeup count",
        const.UOM_FREQUENCY,
        "mdi:sleep-off",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    WithingsAttribute(
        Measurement.SLEEP_WAKEUP_DURATION_SECONDS,
        GetSleepSummaryField.WAKEUP_DURATION,
        "Wakeup time",
        TIME_SECONDS,
        "mdi:sleep-off",
        SENSOR_DOMAIN,
        False,
        UpdateType.POLL,
    ),
    # Webhook measurements.
    WithingsAttribute(
        Measurement.IN_BED,
        NotifyAppli.BED_IN,
        "In bed",
        "",
        "mdi:bed",
        BINARY_SENSOR_DOMAIN,
        True,
        UpdateType.WEBHOOK,
    ),
]

WITHINGS_MEASUREMENTS_MAP: Dict[Measurement, WithingsAttribute] = {
    attr.measurement: attr for attr in WITHINGS_ATTRIBUTES
}

WITHINGS_MEASURE_TYPE_MAP: Dict[
    Union[NotifyAppli, GetSleepSummaryField, MeasureType], WithingsAttribute
] = {attr.measute_type: attr for attr in WITHINGS_ATTRIBUTES}


class ConfigEntryWithingsApi(AbstractWithingsApi):
    """Withing API that uses HA resources."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        implementation: AbstractOAuth2Implementation,
    ):
        """Initialize object."""
        self._hass = hass
        self._config_entry = config_entry
        self._implementation = implementation
        self.session = OAuth2Session(hass, config_entry, implementation)

    def _request(
        self, path: str, params: Dict[str, Any], method: str = "GET"
    ) -> Dict[str, Any]:
        """Perform an async request."""
        asyncio.run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self._hass.loop
        )

        access_token = self._config_entry.data["token"]["access_token"]
        response = requests.request(
            method,
            f"{self.URL}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.json()


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code}, 200)


class WebhookAvailability(IntEnum):
    """Represents various statuses of webhook availability."""

    SUCCESS = 0
    CONNECT_ERROR = 1
    HTTP_ERROR = 2
    NOT_WEBHOOK = 3


class WebhookUpdateCoordinator:
    """Coordinates webhook data updates across listeners."""

    def __init__(self, hass: HomeAssistant, user_id: int) -> None:
        """Initialize the object."""
        self._hass = hass
        self._user_id = user_id
        self._listeners: List[CALLBACK_TYPE] = []
        self.data: MeasurementData = {}

    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Add a listener."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            self.async_remove_listener(listener)

        return remove_listener

    def async_remove_listener(self, listener: CALLBACK_TYPE) -> None:
        """Remove a listener."""
        self._listeners.remove(listener)

    def update_data(self, measurement: Measurement, value: Any) -> None:
        """Update the data object and notify listeners the data has changed."""
        self.data[measurement] = value
        self.notify_data_changed()

    def notify_data_changed(self) -> None:
        """Notify all listeners the data has changed."""
        for listener in self._listeners:
            listener()


class DataManager:
    """Manage withing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        profile: str,
        api: ConfigEntryWithingsApi,
        user_id: int,
        webhook_config: WebhookConfig,
    ):
        """Initialize the data manager."""
        self._hass = hass
        self._api = api
        self._user_id = user_id
        self._profile = profile
        self._webhook_config = webhook_config
        self._notify_subscribe_delay = datetime.timedelta(seconds=10)
        self._notify_unsubscribe_delay = datetime.timedelta(seconds=1)

        self._is_available = True
        self._cancel_interval_update_interval: Optional[CALLBACK_TYPE] = None
        self._cancel_configure_webhook_subscribe_interval: Optional[
            CALLBACK_TYPE
        ] = None
        self._api_notification_id = f"withings_{self._user_id}"

        self.subscription_update_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="subscription_update_coordinator",
            update_interval=timedelta(minutes=120),
            update_method=self.async_subscribe_webhook,
        )
        self.poll_data_update_coordinator = DataUpdateCoordinator[
            Dict[MeasureType, Any]
        ](
            hass,
            _LOGGER,
            name="poll_data_update_coordinator",
            update_interval=timedelta(minutes=30),
            update_method=self.async_get_all_data,
        )
        self.webhook_update_coordinator = WebhookUpdateCoordinator(
            self._hass, self._user_id
        )
        self._cancel_subscription_update: Optional[Callable[[], None]] = None
        self._subscribe_webhook_run_count = 0

    @property
    def webhook_config(self) -> WebhookConfig:
        """Get the webhook config."""
        return self._webhook_config

    @property
    def user_id(self) -> int:
        """Get the user_id of the authenticated user."""
        return self._user_id

    @property
    def profile(self) -> str:
        """Get the profile."""
        return self._profile

    def async_start_polling_webhook_subscriptions(self) -> None:
        """Start polling webhook subscriptions (if enabled) to reconcile their setup."""
        if not self._webhook_config.enabled:
            return

        self.async_stop_polling_webhook_subscriptions()

        def empty_listener() -> None:
            pass

        self._cancel_subscription_update = (
            self.subscription_update_coordinator.async_add_listener(empty_listener)
        )

    def async_stop_polling_webhook_subscriptions(self) -> None:
        """Stop polling webhook subscriptions."""
        if self._cancel_subscription_update:
            self._cancel_subscription_update()
            self._cancel_subscription_update = None

    async def _do_retry(
        self,
        func: Callable[[Any], Any],
        args: Tuple[Any, Any] = (),
        attempts: int = 3,
        call_delay_seconds: float = 0.1,
    ) -> Any:
        async def async_do_it(*args: Any) -> Any:
            return await self._hass.async_add_executor_job(func, *args)

        return await self._async_do_retry(
            async_do_it,
            args=args,
            attempts=attempts,
            call_delay_seconds=call_delay_seconds,
        )

    async def _async_do_retry(
        self,
        func: Callable[[Any], Awaitable[Any]],
        args: Tuple[Any, Any] = (),
        attempts: int = 3,
        call_delay_seconds: float = 0.1,
    ) -> Any:
        """Retry a function call.

        Withings' API occasionally and incorrectly throws errors. Retrying the call tends to work.
        """
        exception = None
        for attempt in range(1, attempts + 1):
            _LOGGER.debug("Attempt %s of %s", attempt, attempts)
            try:
                return await func(*args)
            except Exception as exception1:  # pylint: disable=broad-except
                await asyncio.sleep(call_delay_seconds)
                exception = exception1
                continue

        if exception:
            raise exception

    async def async_subscribe_webhook(self) -> None:
        """Subscribe the webhook to withings data updates."""
        if not self._webhook_config.enabled:
            return

        _LOGGER.debug("Configuring withings webhook")

        call_delay_seconds = self._notify_subscribe_delay.total_seconds()
        enabled_webhook_config = cast(EnabledWebhookConfig, self._webhook_config)
        webhook_url = enabled_webhook_config.url

        response = await self._do_retry(
            self._api.notify_list,
            call_delay_seconds=call_delay_seconds,
        )

        subscribed_applis = frozenset(
            [
                profile.appli
                for profile in response.profiles
                if profile.callbackurl == webhook_url
            ]
        )

        # Determine what subscriptions need to be created.
        ignored_applis = frozenset({NotifyAppli.USER})
        to_add_applis = frozenset(
            [
                appli
                for appli in NotifyAppli
                if appli not in subscribed_applis and appli not in ignored_applis
            ]
        )

        # Subscribe to each one.
        for appli in to_add_applis:
            _LOGGER.debug(
                "Subscribing %s to %s with webhook %s in %s seconds",
                self._profile,
                appli,
                webhook_url,
                call_delay_seconds,
            )

            # Withings will HTTP HEAD the callback_url and needs some downtime
            # between each call or there is a higher chance of failure.
            await asyncio.sleep(call_delay_seconds)
            try:
                await self._do_retry(
                    self._api.notify_subscribe,
                    args=(webhook_url, appli),
                    call_delay_seconds=call_delay_seconds,
                )
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "Subscribing failed %s to %s with webhook %s",
                    self._profile,
                    appli,
                    webhook_url,
                )
                _LOGGER.exception(exception)

    async def async_unsubscribe_webhook(self) -> None:
        """Unsubscribe webhook from withings data updates."""
        call_delay_seconds = self._notify_subscribe_delay.total_seconds()

        # Get the current webhooks.
        response = await self._do_retry(
            self._api.notify_list,
            call_delay_seconds=call_delay_seconds,
        )

        # Revoke subscriptions.
        for profile in response.profiles:
            _LOGGER.debug(
                "Unsubscribing %s to %s with webhook %s in %s seconds",
                self._profile,
                profile.appli,
                profile.callbackurl,
                call_delay_seconds,
            )

            # Quick calls to Withings can result in the service returning errors. Give them
            # some time to cool down.
            await asyncio.sleep(call_delay_seconds)
            try:
                await self._do_retry(
                    self._api.notify_revoke,
                    args=(profile.callbackurl, profile.appli),
                    call_delay_seconds=call_delay_seconds,
                )
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "Unsubscribing failed %s to %s with webhook %s",
                    self._profile,
                    profile.appli,
                    profile.callbackurl,
                )
                _LOGGER.exception(exception)

    def _get_reauth_flow_context(self) -> Dict:
        return {
            const.PROFILE: self._profile,
            "userid": self._user_id,
            "source": "reauth",
        }

    def _get_existing_reauth_flow(self, context: Dict) -> Dict:
        existing_flow = next(
            iter(
                flow
                for flow in self._hass.config_entries.flow.async_progress()
                if context.items() <= flow.get("context").items()
            ),
            None,
        )
        return existing_flow

    async def async_get_all_data(self) -> Optional[Dict[MeasureType, Any]]:
        """Update all withings data."""

        reauth_context = self._get_reauth_flow_context()
        try:
            result = await self._async_do_retry(self._async_get_all_data)

            # Cancel a reauth if Withings is working normally again.
            # Withings occasionally will return an auth error when in fact reauth is not necessary.
            flow = self._get_existing_reauth_flow(reauth_context)
            if flow:
                self._hass.config_entries.flow.async_abort(flow["flow_id"])

            return result
        except Exception as exception:
            # User is not authenticated.
            if isinstance(
                exception, (UnauthorizedException, AuthFailedException)
            ) or NOT_AUTHENTICATED_ERROR.match(str(exception)):
                if self._get_existing_reauth_flow(reauth_context):
                    print("Exiting flow already exists.")
                    return

                # Start a reauth flow.
                _LOGGER.debug("Starting reauth flow for %s", self._profile)
                await self._hass.config_entries.flow.async_init(
                    const.DOMAIN,
                    context=reauth_context,
                )
                return

            raise exception

    async def _async_get_all_data(self) -> Optional[Dict[MeasureType, Any]]:
        _LOGGER.info("Updating all withings data")
        return {
            **await self.async_get_measures(),
            **await self.async_get_sleep_summary(),
        }

    async def async_get_measures(self) -> Dict[MeasureType, Any]:
        """Get the measures data."""
        _LOGGER.debug("Updating withings measures")

        response = await self._hass.async_add_executor_job(self._api.measure_get_meas)

        # Sort from oldest to newest.
        groups = sorted(
            query_measure_groups(
                response, MeasureTypes.ANY, MeasureGroupAttribs.UNAMBIGUOUS
            ),
            key=lambda group: group.created.datetime,
            reverse=False,
        )

        return {
            WITHINGS_MEASURE_TYPE_MAP[measure.type].measurement: round(
                float(measure.value * pow(10, measure.unit)), 2
            )
            for group in groups
            for measure in group.measures
        }

    async def async_get_sleep_summary(self) -> Dict[MeasureType, Any]:
        """Get the sleep summary data."""
        _LOGGER.debug("Updating withing sleep summary")
        now = dt.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = datetime.datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            12,
            0,
            0,
            0,
            datetime.timezone.utc,
        )

        def get_sleep_summary() -> SleepGetSummaryResponse:
            return self._api.sleep_get_summary(
                lastupdate=yesterday_noon,
                data_fields=[
                    GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY,
                    GetSleepSummaryField.DEEP_SLEEP_DURATION,
                    GetSleepSummaryField.DURATION_TO_SLEEP,
                    GetSleepSummaryField.DURATION_TO_WAKEUP,
                    GetSleepSummaryField.HR_AVERAGE,
                    GetSleepSummaryField.HR_MAX,
                    GetSleepSummaryField.HR_MIN,
                    GetSleepSummaryField.LIGHT_SLEEP_DURATION,
                    GetSleepSummaryField.REM_SLEEP_DURATION,
                    GetSleepSummaryField.RR_AVERAGE,
                    GetSleepSummaryField.RR_MAX,
                    GetSleepSummaryField.RR_MIN,
                    GetSleepSummaryField.SLEEP_SCORE,
                    GetSleepSummaryField.SNORING,
                    GetSleepSummaryField.SNORING_EPISODE_COUNT,
                    GetSleepSummaryField.WAKEUP_COUNT,
                    GetSleepSummaryField.WAKEUP_DURATION,
                ],
            )

        response = await self._hass.async_add_executor_job(get_sleep_summary)

        # Set the default to empty lists.
        raw_values: Dict[GetSleepSummaryField, List[int]] = {
            field: [] for field in GetSleepSummaryField
        }

        # Collect the raw data.
        for serie in response.series:
            data = serie.data

            for field in GetSleepSummaryField:
                raw_values[field].append(data._asdict()[field.value])

        values: Dict[GetSleepSummaryField, float] = {}

        def average(data: List[int]) -> float:
            return sum(data) / len(data)

        def set_value(field: GetSleepSummaryField, func: Callable) -> None:
            non_nones = [
                value for value in raw_values.get(field, []) if value is not None
            ]
            values[field] = func(non_nones) if non_nones else None

        set_value(GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY, average)
        set_value(GetSleepSummaryField.DEEP_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.DURATION_TO_SLEEP, average)
        set_value(GetSleepSummaryField.DURATION_TO_WAKEUP, average)
        set_value(GetSleepSummaryField.HR_AVERAGE, average)
        set_value(GetSleepSummaryField.HR_MAX, average)
        set_value(GetSleepSummaryField.HR_MIN, average)
        set_value(GetSleepSummaryField.LIGHT_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.REM_SLEEP_DURATION, sum)
        set_value(GetSleepSummaryField.RR_AVERAGE, average)
        set_value(GetSleepSummaryField.RR_MAX, average)
        set_value(GetSleepSummaryField.RR_MIN, average)
        set_value(GetSleepSummaryField.SLEEP_SCORE, max)
        set_value(GetSleepSummaryField.SNORING, average)
        set_value(GetSleepSummaryField.SNORING_EPISODE_COUNT, sum)
        set_value(GetSleepSummaryField.WAKEUP_COUNT, sum)
        set_value(GetSleepSummaryField.WAKEUP_DURATION, average)

        return {
            WITHINGS_MEASURE_TYPE_MAP[field].measurement: round(value, 4)
            if value is not None
            else None
            for field, value in values.items()
        }

    async def async_webhook_data_updated(self, data_category: NotifyAppli) -> None:
        """Handle scenario when data is updated from a webook."""
        _LOGGER.debug("Withings webhook triggered")
        if data_category in {
            NotifyAppli.WEIGHT,
            NotifyAppli.CIRCULATORY,
            NotifyAppli.SLEEP,
        }:
            await self.poll_data_update_coordinator.async_request_refresh()

        elif data_category in {NotifyAppli.BED_IN, NotifyAppli.BED_OUT}:
            self.webhook_update_coordinator.update_data(
                Measurement.IN_BED, data_category == NotifyAppli.BED_IN
            )


def get_attribute_unique_id(attribute: WithingsAttribute, user_id: int) -> str:
    """Get a entity unique id for a user's attribute."""
    return f"withings_{user_id}_{attribute.measurement.value}"


async def async_get_entity_id(
    hass: HomeAssistant, attribute: WithingsAttribute, user_id: int
) -> Optional[str]:
    """Get an entity id for a user's attribute."""
    entity_registry: EntityRegistry = (
        await hass.helpers.entity_registry.async_get_registry()
    )
    unique_id = get_attribute_unique_id(attribute, user_id)

    entity_id = entity_registry.async_get_entity_id(
        attribute.platform, const.DOMAIN, unique_id
    )

    if entity_id is None:
        _LOGGER.error("Cannot find entity id for unique_id: %s", unique_id)
        return None

    return entity_id


class BaseWithingsSensor(Entity):
    """Base class for withings sensors."""

    def __init__(self, data_manager: DataManager, attribute: WithingsAttribute) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self._attribute = attribute
        self._profile = self._data_manager.profile
        self._user_id = self._data_manager.user_id
        self._name = f"Withings {self._attribute.measurement.value} {self._profile}"
        self._unique_id = get_attribute_unique_id(self._attribute, self._user_id)
        self._state_data: Optional[Any] = None

    @property
    def should_poll(self) -> bool:
        """Return False to indicate HA should not poll for changes."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._attribute.update_type == UpdateType.POLL:
            return self._data_manager.poll_data_update_coordinator.last_update_success

        if self._attribute.update_type == UpdateType.WEBHOOK:
            return self._data_manager.webhook_config.enabled and (
                self._attribute.measurement
                in self._data_manager.webhook_update_coordinator.data
            )

        return True

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._attribute.unit_of_measurement

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._attribute.icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._attribute.enabled_by_default

    @callback
    def _on_poll_data_updated(self) -> None:
        self._update_state_data(
            self._data_manager.poll_data_update_coordinator.data or {}
        )

    @callback
    def _on_webhook_data_updated(self) -> None:
        self._update_state_data(
            self._data_manager.webhook_update_coordinator.data or {}
        )

    def _update_state_data(self, data: MeasurementData) -> None:
        """Update the state data."""
        self._state_data = data.get(self._attribute.measurement)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        if self._attribute.update_type == UpdateType.POLL:
            self.async_on_remove(
                self._data_manager.poll_data_update_coordinator.async_add_listener(
                    self._on_poll_data_updated
                )
            )
            self._on_poll_data_updated()

        elif self._attribute.update_type == UpdateType.WEBHOOK:
            self.async_on_remove(
                self._data_manager.webhook_update_coordinator.async_add_listener(
                    self._on_webhook_data_updated
                )
            )
            self._on_webhook_data_updated()


async def async_init_data_manager(
    hass: HomeAssistant, config_entry: ConfigEntry, webhook_config: WebhookConfig
) -> DataManager:
    """Initialize a new data manager."""
    config_entry_data = get_config_entry_data(hass, config_entry)

    profile = config_entry.data.get(const.PROFILE)

    config_entry_data.data_manager = DataManager(
        hass,
        profile,
        ConfigEntryWithingsApi(
            hass=hass,
            config_entry=config_entry,
            implementation=await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            ),
        ),
        config_entry.data["token"]["userid"],
        webhook_config,
    )

    return await async_get_data_manager(hass, config_entry)


async def async_get_data_manager(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DataManager:
    """Get the data manager for a config entry."""
    return get_config_entry_data(hass, config_entry).data_manager


@dataclass
class ConfigEntryData:
    """Holds data related to a config entry."""

    data_manager: Optional[DataManager] = None


def init_config_entry_data(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Init config entry data."""
    hass.data[const.DOMAIN][CONFIG_ENTRY_DATA][
        config_entry.entry_id
    ] = ConfigEntryData()


def remove_config_entry_data(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove config entry data."""
    del hass.data[const.DOMAIN][CONFIG_ENTRY_DATA][config_entry.entry_id]


def get_config_entry_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> ConfigEntryData:
    """Get config entry data."""
    return hass.data[const.DOMAIN][CONFIG_ENTRY_DATA][config_entry.entry_id]


async def async_register_webhook_config(
    hass: HomeAssistant, config_entry: ConfigEntry, webhook_handler: Callable
) -> WebhookConfig:
    """Register a webhook config."""
    use_webhook = config_entry.options.get(CONF_USE_WEBHOOK, False)
    webhook_id = config_entry.data.get(CONF_WEBHOOK_ID)
    cloudhook_url = config_entry.data.get(CONF_CLOUDHOOK_URL)

    if use_webhook:
        if not webhook_id:
            webhook_id = webhook.async_generate_id()

        is_cloud = hass.components.cloud.async_active_subscription()
        if is_cloud:
            if not cloudhook_url:
                # Delete the existing hook (if exists) because don't have the URL.
                # try:
                #     await hass.components.cloud.async_delete_cloudhook(webhook_id)
                # except ValueError:
                #     pass

                cloudhook_url = await hass.components.cloud.async_create_cloudhook(
                    webhook_id
                )
            webhook_url = cloudhook_url
        else:
            webhook_url = webhook.async_generate_url(hass, webhook_id)

        webhook.async_register(
            hass,
            const.DOMAIN,
            "Withings notify",
            webhook_id,
            webhook_handler,
        )

        webhook_config = EnabledWebhookConfig(
            id=webhook_id, url=webhook_url, is_cloud=is_cloud, enabled=True
        )
    else:
        webhook_config = DISABLED_WEBHOOK_CONFIG

    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            **{
                CONF_WEBHOOK_ID: webhook_id,
                CONF_CLOUDHOOK_URL: cloudhook_url,
            },
        },
    )

    return webhook_config


async def async_unregister_webhook_config(
    hass: HomeAssistant, webhook_config: WebhookConfig
) -> None:
    """Unregister a webhook config."""
    if not webhook_config.enabled:
        return

    enabled_config = cast(EnabledWebhookConfig, webhook_config)
    if enabled_config.is_cloud:
        # Delete the existing hook (if exists)
        try:
            await hass.components.cloud.async_delete_cloudhook(enabled_config.id)
        except ValueError:
            pass

    async_unregister_webhook(hass, enabled_config.id)


def get_data_manager_by_webhook_id(
    hass: HomeAssistant, webhook_id: str
) -> Optional[DataManager]:
    """Get a data manager by it's webhook id."""
    for data_manager in get_all_data_managers(hass):
        if not data_manager.webhook_config.enabled:
            continue

        enabled_webhook_config = cast(EnabledWebhookConfig, data_manager.webhook_config)
        if enabled_webhook_config.id == webhook_id:
            return data_manager


def get_all_data_managers(hass: HomeAssistant) -> Tuple[DataManager, ...]:
    """Get all configured data managers."""
    return tuple(
        [
            config_entry_data.data_manager
            for config_entry_data in hass.data[const.DOMAIN][CONFIG_ENTRY_DATA].values()
            if config_entry_data
        ]
    )


def async_remove_data_manager(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove a data manager for a config entry."""
    get_config_entry_data(hass, config_entry).data_manager = None


async def async_create_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    create_func: Callable[[DataManager, WithingsAttribute], Entity],
    platform: str,
) -> List[Entity]:
    """Create withings entities from config entry."""
    data_manager = await async_get_data_manager(hass, entry)

    return [
        create_func(data_manager, attribute)
        for attribute in get_platform_attributes(platform)
    ]


def get_platform_attributes(platform: str) -> Tuple[WithingsAttribute, ...]:
    """Get withings attributes used for a specific platform."""
    return tuple(
        [
            attribute
            for attribute in WITHINGS_ATTRIBUTES
            if attribute.platform == platform
        ]
    )


class WithingsLocalOAuth2Implementation(LocalOAuth2Implementation):
    """Oauth2 implementation that only uses the external url."""

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        url = get_url(self.hass, allow_internal=False, prefer_cloud=True)
        return f"{url}{AUTH_CALLBACK_PATH}"

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "action": "requesttoken",
                "grant_type": "authorization_code",
                "code": external_data,
                "redirect_uri": self.redirect_uri,
            }
        )

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        return {**token, **new_token}

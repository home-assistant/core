"""Common code for Withings."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import datetime
from datetime import timedelta
from enum import IntEnum, StrEnum
from http import HTTPStatus
import re
from typing import Any

from aiohttp.web import Response
from withings_api.common import (
    AuthFailedException,
    GetSleepSummaryField,
    MeasureGroupAttribs,
    MeasureType,
    MeasureTypes,
    NotifyAppli,
    UnauthorizedException,
    query_measure_groups,
)

from homeassistant.components import webhook
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import const
from .api import ConfigEntryWithingsApi
from .const import LOGGER, Measurement

NOT_AUTHENTICATED_ERROR = re.compile(
    f"^{HTTPStatus.UNAUTHORIZED},.*",
    re.IGNORECASE,
)
DATA_UPDATED_SIGNAL = "withings_entity_state_updated"
SUBSCRIBE_DELAY = datetime.timedelta(seconds=5)
UNSUBSCRIBE_DELAY = datetime.timedelta(seconds=1)


class UpdateType(StrEnum):
    """Data update type."""

    POLL = "poll"
    WEBHOOK = "webhook"


@dataclass
class WebhookConfig:
    """Config for a webhook."""

    id: str
    url: str
    enabled: bool


WITHINGS_MEASURE_TYPE_MAP: dict[
    NotifyAppli | GetSleepSummaryField | MeasureType, Measurement
] = {
    MeasureType.WEIGHT: Measurement.WEIGHT_KG,
    MeasureType.FAT_MASS_WEIGHT: Measurement.FAT_MASS_KG,
    MeasureType.FAT_FREE_MASS: Measurement.FAT_FREE_MASS_KG,
    MeasureType.MUSCLE_MASS: Measurement.MUSCLE_MASS_KG,
    MeasureType.BONE_MASS: Measurement.BONE_MASS_KG,
    MeasureType.HEIGHT: Measurement.HEIGHT_M,
    MeasureType.TEMPERATURE: Measurement.TEMP_C,
    MeasureType.BODY_TEMPERATURE: Measurement.BODY_TEMP_C,
    MeasureType.SKIN_TEMPERATURE: Measurement.SKIN_TEMP_C,
    MeasureType.FAT_RATIO: Measurement.FAT_RATIO_PCT,
    MeasureType.DIASTOLIC_BLOOD_PRESSURE: Measurement.DIASTOLIC_MMHG,
    MeasureType.SYSTOLIC_BLOOD_PRESSURE: Measurement.SYSTOLIC_MMGH,
    MeasureType.HEART_RATE: Measurement.HEART_PULSE_BPM,
    MeasureType.SP02: Measurement.SPO2_PCT,
    MeasureType.HYDRATION: Measurement.HYDRATION,
    MeasureType.PULSE_WAVE_VELOCITY: Measurement.PWV,
    GetSleepSummaryField.BREATHING_DISTURBANCES_INTENSITY: (
        Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY
    ),
    GetSleepSummaryField.DEEP_SLEEP_DURATION: Measurement.SLEEP_DEEP_DURATION_SECONDS,
    GetSleepSummaryField.DURATION_TO_SLEEP: Measurement.SLEEP_TOSLEEP_DURATION_SECONDS,
    GetSleepSummaryField.DURATION_TO_WAKEUP: (
        Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS
    ),
    GetSleepSummaryField.HR_AVERAGE: Measurement.SLEEP_HEART_RATE_AVERAGE,
    GetSleepSummaryField.HR_MAX: Measurement.SLEEP_HEART_RATE_MAX,
    GetSleepSummaryField.HR_MIN: Measurement.SLEEP_HEART_RATE_MIN,
    GetSleepSummaryField.LIGHT_SLEEP_DURATION: Measurement.SLEEP_LIGHT_DURATION_SECONDS,
    GetSleepSummaryField.REM_SLEEP_DURATION: Measurement.SLEEP_REM_DURATION_SECONDS,
    GetSleepSummaryField.RR_AVERAGE: Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE,
    GetSleepSummaryField.RR_MAX: Measurement.SLEEP_RESPIRATORY_RATE_MAX,
    GetSleepSummaryField.RR_MIN: Measurement.SLEEP_RESPIRATORY_RATE_MIN,
    GetSleepSummaryField.SLEEP_SCORE: Measurement.SLEEP_SCORE,
    GetSleepSummaryField.SNORING: Measurement.SLEEP_SNORING,
    GetSleepSummaryField.SNORING_EPISODE_COUNT: Measurement.SLEEP_SNORING_EPISODE_COUNT,
    GetSleepSummaryField.WAKEUP_COUNT: Measurement.SLEEP_WAKEUP_COUNT,
    GetSleepSummaryField.WAKEUP_DURATION: Measurement.SLEEP_WAKEUP_DURATION_SECONDS,
    NotifyAppli.BED_IN: Measurement.IN_BED,
}


def json_message_response(message: str, message_code: int) -> Response:
    """Produce common json output."""
    return HomeAssistantView.json({"message": message, "code": message_code})


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
        self._listeners: list[CALLBACK_TYPE] = []
        self.data: dict[Measurement, Any] = {}

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
        api: ConfigEntryWithingsApi,
        user_id: int,
        webhook_config: WebhookConfig,
    ) -> None:
        """Initialize the data manager."""
        self._hass = hass
        self._api = api
        self._user_id = user_id
        self._webhook_config = webhook_config
        self._notify_subscribe_delay = SUBSCRIBE_DELAY
        self._notify_unsubscribe_delay = UNSUBSCRIBE_DELAY

        self._is_available = True
        self._cancel_interval_update_interval: CALLBACK_TYPE | None = None
        self._cancel_configure_webhook_subscribe_interval: CALLBACK_TYPE | None = None
        self._api_notification_id = f"withings_{self._user_id}"

        self.subscription_update_coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name="subscription_update_coordinator",
            update_interval=timedelta(minutes=120),
            update_method=self.async_subscribe_webhook,
        )
        self.poll_data_update_coordinator = DataUpdateCoordinator[
            dict[MeasureType, Any] | None
        ](
            hass,
            LOGGER,
            name="poll_data_update_coordinator",
            update_interval=timedelta(minutes=120)
            if self._webhook_config.enabled
            else timedelta(minutes=10),
            update_method=self.async_get_all_data,
        )
        self.webhook_update_coordinator = WebhookUpdateCoordinator(
            self._hass, self._user_id
        )
        self._cancel_subscription_update: Callable[[], None] | None = None
        self._subscribe_webhook_run_count = 0

    @property
    def webhook_config(self) -> WebhookConfig:
        """Get the webhook config."""
        return self._webhook_config

    @property
    def user_id(self) -> int:
        """Get the user_id of the authenticated user."""
        return self._user_id

    def async_start_polling_webhook_subscriptions(self) -> None:
        """Start polling webhook subscriptions (if enabled) to reconcile their setup."""
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

    async def async_subscribe_webhook(self) -> None:
        """Subscribe the webhook to withings data updates."""
        LOGGER.debug("Configuring withings webhook")

        # On first startup, perform a fresh re-subscribe. Withings stops pushing data
        # if the webhook fails enough times but they don't remove the old subscription
        # config. This ensures the subscription is setup correctly and they start
        # pushing again.
        if self._subscribe_webhook_run_count == 0:
            LOGGER.debug("Refreshing withings webhook configs")
            await self.async_unsubscribe_webhook()
        self._subscribe_webhook_run_count += 1

        # Get the current webhooks.
        response = await self._api.async_notify_list()

        subscribed_applis = frozenset(
            profile.appli
            for profile in response.profiles
            if profile.callbackurl == self._webhook_config.url
        )

        # Determine what subscriptions need to be created.
        ignored_applis = frozenset({NotifyAppli.USER, NotifyAppli.UNKNOWN})
        to_add_applis = frozenset(
            appli
            for appli in NotifyAppli
            if appli not in subscribed_applis and appli not in ignored_applis
        )

        # Subscribe to each one.
        for appli in to_add_applis:
            LOGGER.debug(
                "Subscribing %s for %s in %s seconds",
                self._webhook_config.url,
                appli,
                self._notify_subscribe_delay.total_seconds(),
            )
            # Withings will HTTP HEAD the callback_url and needs some downtime
            # between each call or there is a higher chance of failure.
            await asyncio.sleep(self._notify_subscribe_delay.total_seconds())
            await self._api.async_notify_subscribe(self._webhook_config.url, appli)

    async def async_unsubscribe_webhook(self) -> None:
        """Unsubscribe webhook from withings data updates."""
        # Get the current webhooks.
        response = await self._api.async_notify_list()

        # Revoke subscriptions.
        for profile in response.profiles:
            LOGGER.debug(
                "Unsubscribing %s for %s in %s seconds",
                profile.callbackurl,
                profile.appli,
                self._notify_unsubscribe_delay.total_seconds(),
            )
            # Quick calls to Withings can result in the service returning errors.
            # Give them some time to cool down.
            await asyncio.sleep(self._notify_subscribe_delay.total_seconds())
            await self._api.async_notify_revoke(profile.callbackurl, profile.appli)

    async def async_get_all_data(self) -> dict[MeasureType, Any] | None:
        """Update all withings data."""
        try:
            return {
                **await self.async_get_measures(),
                **await self.async_get_sleep_summary(),
            }
        except Exception as exception:
            # User is not authenticated.
            if isinstance(
                exception, (UnauthorizedException, AuthFailedException)
            ) or NOT_AUTHENTICATED_ERROR.match(str(exception)):
                self._api.config_entry.async_start_reauth(self._hass)
                return None

            raise exception

    async def async_get_measures(self) -> dict[Measurement, Any]:
        """Get the measures data."""
        LOGGER.debug("Updating withings measures")
        now = dt_util.utcnow()
        startdate = now - datetime.timedelta(days=7)

        response = await self._api.async_measure_get_meas(
            None, None, startdate, now, None, startdate
        )

        # Sort from oldest to newest.
        groups = sorted(
            query_measure_groups(
                response, MeasureTypes.ANY, MeasureGroupAttribs.UNAMBIGUOUS
            ),
            key=lambda group: group.created.datetime,
            reverse=False,
        )

        return {
            WITHINGS_MEASURE_TYPE_MAP[measure.type]: round(
                float(measure.value * pow(10, measure.unit)), 2
            )
            for group in groups
            for measure in group.measures
            if measure.type in WITHINGS_MEASURE_TYPE_MAP
        }

    async def async_get_sleep_summary(self) -> dict[Measurement, Any]:
        """Get the sleep summary data."""
        LOGGER.debug("Updating withing sleep summary")
        now = dt_util.now()
        yesterday = now - datetime.timedelta(days=1)
        yesterday_noon = dt_util.start_of_local_day(yesterday) + datetime.timedelta(
            hours=12
        )
        yesterday_noon_utc = dt_util.as_utc(yesterday_noon)

        response = await self._api.async_sleep_get_summary(
            lastupdate=yesterday_noon_utc,
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

        # Set the default to empty lists.
        raw_values: dict[GetSleepSummaryField, list[int]] = {
            field: [] for field in GetSleepSummaryField
        }

        # Collect the raw data.
        for serie in response.series:
            data = serie.data

            for field in GetSleepSummaryField:
                raw_values[field].append(dict(data)[field.value])

        values: dict[GetSleepSummaryField, float] = {}

        def average(data: list[int]) -> float:
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
            WITHINGS_MEASURE_TYPE_MAP[field]: round(value, 4)
            if value is not None
            else None
            for field, value in values.items()
        }

    async def async_webhook_data_updated(self, data_category: NotifyAppli) -> None:
        """Handle scenario when data is updated from a webook."""
        LOGGER.debug("Withings webhook triggered")
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


async def async_get_data_manager(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DataManager:
    """Get the data manager for a config entry."""
    hass.data.setdefault(const.DOMAIN, {})
    hass.data[const.DOMAIN].setdefault(config_entry.entry_id, {})
    config_entry_data = hass.data[const.DOMAIN][config_entry.entry_id]

    if const.DATA_MANAGER not in config_entry_data:
        LOGGER.debug(
            "Creating withings data manager for profile: %s", config_entry.title
        )
        config_entry_data[const.DATA_MANAGER] = DataManager(
            hass,
            ConfigEntryWithingsApi(
                hass=hass,
                config_entry=config_entry,
                implementation=await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, config_entry
                ),
            ),
            config_entry.data["token"]["userid"],
            WebhookConfig(
                id=config_entry.data[CONF_WEBHOOK_ID],
                url=webhook.async_generate_url(
                    hass, config_entry.data[CONF_WEBHOOK_ID]
                ),
                enabled=config_entry.options[const.CONF_USE_WEBHOOK],
            ),
        )

    return config_entry_data[const.DATA_MANAGER]


def get_data_manager_by_webhook_id(
    hass: HomeAssistant, webhook_id: str
) -> DataManager | None:
    """Get a data manager by it's webhook id."""
    return next(
        iter(
            [
                data_manager
                for data_manager in get_all_data_managers(hass)
                if data_manager.webhook_config.id == webhook_id
            ]
        ),
        None,
    )


def get_all_data_managers(hass: HomeAssistant) -> tuple[DataManager, ...]:
    """Get all configured data managers."""
    return tuple(
        config_entry_data[const.DATA_MANAGER]
        for config_entry_data in hass.data[const.DOMAIN].values()
        if const.DATA_MANAGER in config_entry_data
    )


def async_remove_data_manager(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove a data manager for a config entry."""
    del hass.data[const.DOMAIN][config_entry.entry_id][const.DATA_MANAGER]

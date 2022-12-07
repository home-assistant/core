"""Support for the Fitbit API."""
from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Final, cast

from aiohttp.web import Request
from fitbit import Fitbit
from fitbit.api import FitbitOauth2Client
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError, MissingTokenError
import voluptuous as vol

from homeassistant.components import configurator
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.json import load_json, save_json
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    ATTR_ACCESS_TOKEN,
    ATTR_LAST_SAVED_AT,
    ATTR_REFRESH_TOKEN,
    ATTRIBUTION,
    BATTERY_LEVELS,
    CONF_CLOCK_FORMAT,
    CONF_MONITORED_RESOURCES,
    DEFAULT_CLOCK_FORMAT,
    DEFAULT_CONFIG,
    FITBIT_AUTH_CALLBACK_PATH,
    FITBIT_AUTH_START,
    FITBIT_CONFIG_FILE,
    FITBIT_DEFAULT_RESOURCES,
    FITBIT_MEASUREMENTS,
    FITBIT_RESOURCE_BATTERY,
    FITBIT_RESOURCES_KEYS,
    FITBIT_RESOURCES_LIST,
    FitbitSensorEntityDescription,
)

_LOGGER: Final = logging.getLogger(__name__)

_CONFIGURING: dict[str, str] = {}

SCAN_INTERVAL: Final = datetime.timedelta(minutes=30)

PLATFORM_SCHEMA: Final = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_MONITORED_RESOURCES, default=FITBIT_DEFAULT_RESOURCES
        ): vol.All(cv.ensure_list, [vol.In(FITBIT_RESOURCES_KEYS)]),
        vol.Optional(CONF_CLOCK_FORMAT, default=DEFAULT_CLOCK_FORMAT): vol.In(
            ["12H", "24H"]
        ),
        vol.Optional(CONF_UNIT_SYSTEM, default="default"): vol.In(
            ["en_GB", "en_US", "metric", "default"]
        ),
    }
)


def request_app_setup(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    config_path: str,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Assist user with configuring the Fitbit dev application."""

    def fitbit_configuration_callback(fields: list[dict[str, str]]) -> None:
        """Handle configuration updates."""
        config_path = hass.config.path(FITBIT_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = load_json(config_path)
            if config_file == DEFAULT_CONFIG:
                error_msg = f"You didn't correctly modify {FITBIT_CONFIG_FILE}, please try again."

                configurator.notify_errors(hass, _CONFIGURING["fitbit"], error_msg)
            else:
                setup_platform(hass, config, add_entities, discovery_info)
        else:
            setup_platform(hass, config, add_entities, discovery_info)

    try:
        description = f"""Please create a Fitbit developer app at
                       https://dev.fitbit.com/apps/new.
                       For the OAuth 2.0 Application Type choose Personal.
                       Set the Callback URL to {get_url(hass, require_ssl=True)}{FITBIT_AUTH_CALLBACK_PATH}.
                       (Note: Your Home Assistant instance must be accessible via HTTPS.)
                       They will provide you a Client ID and secret.
                       These need to be saved into the file located at: {config_path}.
                       Then come back here and hit the below button.
                       """
    except NoURLAvailableError:
        _LOGGER.error(
            "Could not find an SSL enabled URL for your Home Assistant instance. "
            "Fitbit requires that your Home Assistant instance is accessible via HTTPS"
        )
        return

    submit = f"I have saved my Client ID and Client Secret into {FITBIT_CONFIG_FILE}."

    _CONFIGURING["fitbit"] = configurator.request_config(
        hass,
        "Fitbit",
        fitbit_configuration_callback,
        description=description,
        submit_caption=submit,
        description_image="/static/images/config_fitbit_app.png",
    )


def request_oauth_completion(hass: HomeAssistant) -> None:
    """Request user complete Fitbit OAuth2 flow."""
    if "fitbit" in _CONFIGURING:
        configurator.notify_errors(
            hass, _CONFIGURING["fitbit"], "Failed to register, please try again."
        )

        return

    def fitbit_configuration_callback(fields: list[dict[str, str]]) -> None:
        """Handle configuration updates."""

    start_url = f"{get_url(hass, require_ssl=True)}{FITBIT_AUTH_START}"

    description = f"Please authorize Fitbit by visiting {start_url}"

    _CONFIGURING["fitbit"] = configurator.request_config(
        hass,
        "Fitbit",
        fitbit_configuration_callback,
        description=description,
        submit_caption="I have authorized Fitbit.",
    )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fitbit sensor."""
    config_path = hass.config.path(FITBIT_CONFIG_FILE)
    if os.path.isfile(config_path):
        config_file: ConfigType = cast(ConfigType, load_json(config_path))
        if config_file == DEFAULT_CONFIG:
            request_app_setup(
                hass, config, add_entities, config_path, discovery_info=None
            )
            return
    else:
        save_json(config_path, DEFAULT_CONFIG)
        request_app_setup(hass, config, add_entities, config_path, discovery_info=None)
        return

    if "fitbit" in _CONFIGURING:
        configurator.request_done(hass, _CONFIGURING.pop("fitbit"))

    access_token: str | None = config_file.get(ATTR_ACCESS_TOKEN)
    refresh_token: str | None = config_file.get(ATTR_REFRESH_TOKEN)
    expires_at: int | None = config_file.get(ATTR_LAST_SAVED_AT)
    if (
        access_token is not None
        and refresh_token is not None
        and expires_at is not None
    ):
        authd_client = Fitbit(
            config_file.get(CONF_CLIENT_ID),
            config_file.get(CONF_CLIENT_SECRET),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_cb=lambda x: None,
        )

        if int(time.time()) - expires_at > 3600:
            authd_client.client.refresh_token()

        user_profile = authd_client.user_profile_get()["user"]
        if (unit_system := config[CONF_UNIT_SYSTEM]) == "default":
            authd_client.system = user_profile["locale"]
            if authd_client.system != "en_GB":
                if hass.config.units is METRIC_SYSTEM:
                    authd_client.system = "metric"
                else:
                    authd_client.system = "en_US"
        else:
            authd_client.system = unit_system

        registered_devs = authd_client.get_devices()
        clock_format = config[CONF_CLOCK_FORMAT]
        monitored_resources = config[CONF_MONITORED_RESOURCES]
        entities = [
            FitbitSensor(
                authd_client,
                user_profile,
                config_path,
                description,
                hass.config.units is METRIC_SYSTEM,
                clock_format,
            )
            for description in FITBIT_RESOURCES_LIST
            if description.key in monitored_resources
        ]
        if "devices/battery" in monitored_resources:
            entities.extend(
                [
                    FitbitSensor(
                        authd_client,
                        user_profile,
                        config_path,
                        FITBIT_RESOURCE_BATTERY,
                        hass.config.units is METRIC_SYSTEM,
                        clock_format,
                        dev_extra,
                    )
                    for dev_extra in registered_devs
                ]
            )
        add_entities(entities, True)

    else:
        oauth = FitbitOauth2Client(
            config_file.get(CONF_CLIENT_ID), config_file.get(CONF_CLIENT_SECRET)
        )

        redirect_uri = f"{get_url(hass, require_ssl=True)}{FITBIT_AUTH_CALLBACK_PATH}"

        fitbit_auth_start_url, _ = oauth.authorize_token_url(
            redirect_uri=redirect_uri,
            scope=[
                "activity",
                "heartrate",
                "nutrition",
                "profile",
                "settings",
                "sleep",
                "weight",
            ],
        )

        hass.http.register_redirect(FITBIT_AUTH_START, fitbit_auth_start_url)
        hass.http.register_view(FitbitAuthCallbackView(config, add_entities, oauth))

        request_oauth_completion(hass)


class FitbitAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = FITBIT_AUTH_CALLBACK_PATH
    name = "api:fitbit:callback"

    def __init__(
        self,
        config: ConfigType,
        add_entities: AddEntitiesCallback,
        oauth: FitbitOauth2Client,
    ) -> None:
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_entities = add_entities
        self.oauth = oauth

    async def get(self, request: Request) -> str:
        """Finish OAuth callback request."""
        hass: HomeAssistant = request.app["hass"]
        data = request.query

        response_message = """Fitbit has been successfully authorized!
        You can close this window now!"""

        result = None
        if data.get("code") is not None:
            redirect_uri = f"{get_url(hass, require_current_request=True)}{FITBIT_AUTH_CALLBACK_PATH}"

            try:
                result = await hass.async_add_executor_job(
                    self.oauth.fetch_access_token, data.get("code"), redirect_uri
                )
            except MissingTokenError as error:
                _LOGGER.error("Missing token: %s", error)
                response_message = f"""Something went wrong when
                attempting authenticating with Fitbit. The error
                encountered was {error}. Please try again!"""
            except MismatchingStateError as error:
                _LOGGER.error("Mismatched state, CSRF error: %s", error)
                response_message = f"""Something went wrong when
                attempting authenticating with Fitbit. The error
                encountered was {error}. Please try again!"""
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Fitbit.
                An unknown error occurred. Please try again!
                """

        if result is None:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Fitbit.
                An unknown error occurred. Please try again!
                """

        html_response = f"""<html><head><title>Fitbit Auth</title></head>
        <body><h1>{response_message}</h1></body></html>"""

        if result:
            config_contents = {
                ATTR_ACCESS_TOKEN: result.get("access_token"),
                ATTR_REFRESH_TOKEN: result.get("refresh_token"),
                CONF_CLIENT_ID: self.oauth.client_id,
                CONF_CLIENT_SECRET: self.oauth.client_secret,
                ATTR_LAST_SAVED_AT: int(time.time()),
            }
        save_json(hass.config.path(FITBIT_CONFIG_FILE), config_contents)

        hass.async_add_job(setup_platform, hass, self.config, self.add_entities)

        return html_response


class FitbitSensor(SensorEntity):
    """Implementation of a Fitbit sensor."""

    entity_description: FitbitSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        client: Fitbit,
        user_profile: dict[str, Any],
        config_path: str,
        description: FitbitSensorEntityDescription,
        is_metric: bool,
        clock_format: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        """Initialize the Fitbit sensor."""
        self.entity_description = description
        self.client = client
        self.config_path = config_path
        self.is_metric = is_metric
        self.clock_format = clock_format
        self.extra = extra

        self._attr_unique_id = f"{user_profile['encodedId']}_{description.key}"
        if self.extra is not None:
            self._attr_name = f"{self.extra.get('deviceVersion')} Battery"
            self._attr_unique_id = f"{self._attr_unique_id}_{self.extra.get('id')}"

        if (unit_type := description.unit_type) == "":
            split_resource = description.key.rsplit("/", maxsplit=1)[-1]
            try:
                measurement_system = FITBIT_MEASUREMENTS[self.client.system]
            except KeyError:
                if self.is_metric:
                    measurement_system = FITBIT_MEASUREMENTS["metric"]
                else:
                    measurement_system = FITBIT_MEASUREMENTS["en_US"]
            unit_type = measurement_system[split_resource]
        self._attr_native_unit_of_measurement = unit_type

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend, if any."""
        if (
            self.entity_description.key == "devices/battery"
            and self.extra is not None
            and (extra_battery := self.extra.get("battery")) is not None
            and (battery_level := BATTERY_LEVELS.get(extra_battery)) is not None
        ):
            return icon_for_battery_level(battery_level=battery_level)
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        attrs: dict[str, str | None] = {}

        if self.extra is not None:
            attrs["model"] = self.extra.get("deviceVersion")
            extra_type = self.extra.get("type")
            attrs["type"] = extra_type.lower() if extra_type is not None else None

        return attrs

    def update(self) -> None:
        """Get the latest data from the Fitbit API and update the states."""
        resource_type = self.entity_description.key
        if resource_type == "devices/battery" and self.extra is not None:
            registered_devs: list[dict[str, Any]] = self.client.get_devices()
            device_id = self.extra.get("id")
            self.extra = list(
                filter(lambda device: device.get("id") == device_id, registered_devs)
            )[0]
            self._attr_native_value = self.extra.get("battery")

        else:
            container = resource_type.replace("/", "-")
            response = self.client.time_series(resource_type, period="7d")
            raw_state = response[container][-1].get("value")
            if resource_type == "activities/distance":
                self._attr_native_value = format(float(raw_state), ".2f")
            elif resource_type == "activities/tracker/distance":
                self._attr_native_value = format(float(raw_state), ".2f")
            elif resource_type == "body/bmi":
                self._attr_native_value = format(float(raw_state), ".1f")
            elif resource_type == "body/fat":
                self._attr_native_value = format(float(raw_state), ".1f")
            elif resource_type == "body/weight":
                self._attr_native_value = format(float(raw_state), ".1f")
            elif resource_type == "sleep/startTime":
                if raw_state == "":
                    self._attr_native_value = "-"
                elif self.clock_format == "12H":
                    hours, minutes = raw_state.split(":")
                    hours, minutes = int(hours), int(minutes)
                    setting = "AM"
                    if hours > 12:
                        setting = "PM"
                        hours -= 12
                    elif hours == 0:
                        hours = 12
                    self._attr_native_value = f"{hours}:{minutes:02d} {setting}"
                else:
                    self._attr_native_value = raw_state
            else:
                if self.is_metric:
                    self._attr_native_value = raw_state
                else:
                    try:
                        self._attr_native_value = f"{int(raw_state):,}"
                    except TypeError:
                        self._attr_native_value = raw_state

        if resource_type == "activities/heart":
            self._attr_native_value = (
                response[container][-1].get("value").get("restingHeartRate")
            )

        token = self.client.client.session.token
        config_contents = {
            ATTR_ACCESS_TOKEN: token.get("access_token"),
            ATTR_REFRESH_TOKEN: token.get("refresh_token"),
            CONF_CLIENT_ID: self.client.client.client_id,
            CONF_CLIENT_SECRET: self.client.client.client_secret,
            ATTR_LAST_SAVED_AT: int(time.time()),
        }
        save_json(self.config_path, config_contents)

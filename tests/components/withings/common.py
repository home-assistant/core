"""Common data for for the withings component tests."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
import arrow
from withings_api.common import (
    MeasureGetMeasResponse,
    NotifyAppli,
    NotifyListResponse,
    SleepGetSummaryResponse,
    UserGetDeviceResponse,
)

from homeassistant import data_entry_flow
import homeassistant.components.api as api
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
import homeassistant.components.webhook as webhook
from homeassistant.components.withings import async_unload_entry
from homeassistant.components.withings.common import (
    ConfigEntryWithingsApi,
    DataManager,
    get_all_data_managers,
)
import homeassistant.components.withings.const as const
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EXTERNAL_URL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import AUTH_CALLBACK_PATH
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.test_util.aiohttp import AiohttpClientMocker


@dataclass
class ProfileConfig:
    """Data representing a user profile."""

    profile: str
    user_id: int
    api_response_user_get_device: UserGetDeviceResponse | Exception
    api_response_measure_get_meas: MeasureGetMeasResponse | Exception
    api_response_sleep_get_summary: SleepGetSummaryResponse | Exception
    api_response_notify_list: NotifyListResponse | Exception
    api_response_notify_revoke: Exception | None


def new_profile_config(
    profile: str,
    user_id: int,
    api_response_user_get_device: UserGetDeviceResponse | Exception | None = None,
    api_response_measure_get_meas: MeasureGetMeasResponse | Exception | None = None,
    api_response_sleep_get_summary: SleepGetSummaryResponse | Exception | None = None,
    api_response_notify_list: NotifyListResponse | Exception | None = None,
    api_response_notify_revoke: Exception | None = None,
) -> ProfileConfig:
    """Create a new profile config immutable object."""
    return ProfileConfig(
        profile=profile,
        user_id=user_id,
        api_response_user_get_device=api_response_user_get_device
        or UserGetDeviceResponse(devices=[]),
        api_response_measure_get_meas=api_response_measure_get_meas
        or MeasureGetMeasResponse(
            measuregrps=[],
            more=False,
            offset=0,
            timezone=dt_util.UTC,
            updatetime=arrow.get(12345),
        ),
        api_response_sleep_get_summary=api_response_sleep_get_summary
        or SleepGetSummaryResponse(more=False, offset=0, series=[]),
        api_response_notify_list=api_response_notify_list
        or NotifyListResponse(profiles=[]),
        api_response_notify_revoke=api_response_notify_revoke,
    )


@dataclass
class WebhookResponse:
    """Response data from a webhook."""

    message: str
    message_code: int


class ComponentFactory:
    """Manages the setup and unloading of the withing component and profiles."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_class_mock: MagicMock,
        aiohttp_client,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Initialize the object."""
        self._hass = hass
        self._api_class_mock = api_class_mock
        self._aiohttp_client = aiohttp_client
        self._aioclient_mock = aioclient_mock
        self._client_id = None
        self._client_secret = None
        self._profile_configs: tuple[ProfileConfig, ...] = ()

    async def configure_component(
        self,
        client_id: str = "my_client_id",
        client_secret: str = "my_client_secret",
        profile_configs: tuple[ProfileConfig, ...] = (),
    ) -> None:
        """Configure the wihings component."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._profile_configs = profile_configs

        hass_config = {
            "homeassistant": {
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
                CONF_EXTERNAL_URL: "http://127.0.0.1:8080/",
            },
            api.DOMAIN: {},
            const.DOMAIN: {
                CONF_CLIENT_ID: self._client_id,
                CONF_CLIENT_SECRET: self._client_secret,
                const.CONF_USE_WEBHOOK: True,
            },
        }

        await async_process_ha_core_config(self._hass, hass_config.get("homeassistant"))
        assert await async_setup_component(self._hass, HA_DOMAIN, {})
        assert await async_setup_component(self._hass, webhook.DOMAIN, hass_config)

        assert await async_setup_component(self._hass, const.DOMAIN, hass_config)
        await self._hass.async_block_till_done()

    @staticmethod
    def _setup_api_method(api_method, value) -> None:
        if isinstance(value, Exception):
            api_method.side_effect = value
        else:
            api_method.return_value = value

    async def setup_profile(self, user_id: int) -> ConfigEntryWithingsApi:
        """Set up a user profile through config flows."""
        profile_config = next(
            iter(
                [
                    profile_config
                    for profile_config in self._profile_configs
                    if profile_config.user_id == user_id
                ]
            )
        )

        api_mock: ConfigEntryWithingsApi = MagicMock(spec=ConfigEntryWithingsApi)
        ComponentFactory._setup_api_method(
            api_mock.user_get_device, profile_config.api_response_user_get_device
        )
        ComponentFactory._setup_api_method(
            api_mock.sleep_get_summary, profile_config.api_response_sleep_get_summary
        )
        ComponentFactory._setup_api_method(
            api_mock.measure_get_meas, profile_config.api_response_measure_get_meas
        )
        ComponentFactory._setup_api_method(
            api_mock.notify_list, profile_config.api_response_notify_list
        )
        ComponentFactory._setup_api_method(
            api_mock.notify_revoke, profile_config.api_response_notify_revoke
        )

        self._api_class_mock.reset_mocks()
        self._api_class_mock.return_value = api_mock

        # Get the withings config flow.
        result = await self._hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": SOURCE_USER}
        )
        assert result
        # pylint: disable=protected-access
        state = config_entry_oauth2_flow._encode_jwt(
            self._hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "http://127.0.0.1:8080/auth/external/callback",
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert result["url"] == (
            "https://account.withings.com/oauth2_user/authorize2?"
            f"response_type=code&client_id={self._client_id}&"
            "redirect_uri=http://127.0.0.1:8080/auth/external/callback&"
            f"state={state}"
            "&scope=user.info,user.metrics,user.activity,user.sleepevents"
        )

        # Simulate user being redirected from withings site.
        client: TestClient = await self._aiohttp_client(self._hass.http.app)
        resp = await client.get(f"{AUTH_CALLBACK_PATH}?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        self._aioclient_mock.clear_requests()
        self._aioclient_mock.post(
            "https://account.withings.com/oauth2/token",
            json={
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": profile_config.user_id,
            },
        )

        # Present user with a list of profiles to choose from.
        result = await self._hass.config_entries.flow.async_configure(result["flow_id"])
        assert result.get("type") == "form"
        assert result.get("step_id") == "profile"
        assert "profile" in result.get("data_schema").schema

        # Provide the user profile.
        result = await self._hass.config_entries.flow.async_configure(
            result["flow_id"], {const.PROFILE: profile_config.profile}
        )

        # Finish the config flow by calling it again.
        assert result.get("type") == "create_entry"
        assert result.get("result")
        config_data = result.get("result").data
        assert config_data.get(const.PROFILE) == profile_config.profile
        assert config_data.get("auth_implementation") == const.DOMAIN
        assert config_data.get("token")

        # Wait for remaining tasks to complete.
        await self._hass.async_block_till_done()

        # Mock the webhook.
        data_manager = get_data_manager_by_user_id(self._hass, user_id)
        self._aioclient_mock.clear_requests()
        self._aioclient_mock.request(
            "HEAD",
            data_manager.webhook_config.url,
        )

        return self._api_class_mock.return_value

    async def call_webhook(self, user_id: int, appli: NotifyAppli) -> WebhookResponse:
        """Call the webhook to notify of data changes."""
        client: TestClient = await self._aiohttp_client(self._hass.http.app)
        data_manager = get_data_manager_by_user_id(self._hass, user_id)

        resp = await client.post(
            urlparse(data_manager.webhook_config.url).path,
            data={"userid": user_id, "appli": appli.value},
        )

        # Wait for remaining tasks to complete.
        await self._hass.async_block_till_done()

        data = await resp.json()
        resp.close()

        return WebhookResponse(message=data["message"], message_code=data["code"])

    async def unload(self, profile: ProfileConfig) -> None:
        """Unload the component for a specific user."""
        config_entries = get_config_entries_for_user_id(self._hass, profile.user_id)

        for config_entry in config_entries:
            await async_unload_entry(self._hass, config_entry)

        await self._hass.async_block_till_done()

        assert not get_data_manager_by_user_id(self._hass, profile.user_id)


def get_config_entries_for_user_id(
    hass: HomeAssistant, user_id: int
) -> tuple[ConfigEntry]:
    """Get a list of config entries that apply to a specific withings user."""
    return tuple(
        config_entry
        for config_entry in hass.config_entries.async_entries(const.DOMAIN)
        if config_entry.data.get("token", {}).get("userid") == user_id
    )


def async_get_flow_for_user_id(hass: HomeAssistant, user_id: int) -> list[dict]:
    """Get a flow for a user id."""
    return [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == const.DOMAIN and flow["context"].get("userid") == user_id
    ]


def get_data_manager_by_user_id(
    hass: HomeAssistant, user_id: int
) -> DataManager | None:
    """Get a data manager by the user id."""
    return next(
        iter(
            [
                data_manager
                for data_manager in get_all_data_managers(hass)
                if data_manager.user_id == user_id
            ]
        ),
        None,
    )

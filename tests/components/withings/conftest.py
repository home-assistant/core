"""Fixtures for withings tests."""
import time
from typing import Awaitable, Callable, List

import asynctest
import nokia
import pytest

import homeassistant.components.api as api
import homeassistant.components.http as http
import homeassistant.components.withings.const as const
from homeassistant.components.withings import CONFIG_SCHEMA, DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC
from homeassistant.setup import async_setup_component

from .common import (
    NOKIA_MEASURES_RESPONSE,
    NOKIA_SLEEP_RESPONSE,
    NOKIA_SLEEP_SUMMARY_RESPONSE,
)


class WithingsFactoryConfig:
    """Configuration for withings test fixture."""

    PROFILE_1 = "Person 1"
    PROFILE_2 = "Person 2"

    def __init__(
        self,
        api_config: dict = None,
        http_config: dict = None,
        measures: List[str] = None,
        unit_system: str = None,
        throttle_interval: int = const.THROTTLE_INTERVAL,
        nokia_request_response="DATA",
        nokia_measures_response: nokia.NokiaMeasures = NOKIA_MEASURES_RESPONSE,
        nokia_sleep_response: nokia.NokiaSleep = NOKIA_SLEEP_RESPONSE,
        nokia_sleep_summary_response: nokia.NokiaSleepSummary = NOKIA_SLEEP_SUMMARY_RESPONSE,
    ) -> None:
        """Constructor."""
        self._throttle_interval = throttle_interval
        self._nokia_request_response = nokia_request_response
        self._nokia_measures_response = nokia_measures_response
        self._nokia_sleep_response = nokia_sleep_response
        self._nokia_sleep_summary_response = nokia_sleep_summary_response
        self._withings_config = {
            const.CLIENT_ID: "my_client_id",
            const.CLIENT_SECRET: "my_client_secret",
            const.PROFILES: [
                WithingsFactoryConfig.PROFILE_1,
                WithingsFactoryConfig.PROFILE_2,
            ],
        }

        self._api_config = api_config or {"base_url": "http://localhost/"}
        self._http_config = http_config or {}
        self._measures = measures

        assert self._withings_config, "withings_config must be set."
        assert isinstance(
            self._withings_config, dict
        ), "withings_config must be a dict."
        assert isinstance(self._api_config, dict), "api_config must be a dict."
        assert isinstance(self._http_config, dict), "http_config must be a dict."

        self._hass_config = {
            "homeassistant": {CONF_UNIT_SYSTEM: unit_system or CONF_UNIT_SYSTEM_METRIC},
            api.DOMAIN: self._api_config,
            http.DOMAIN: self._http_config,
            DOMAIN: self._withings_config,
        }

    @property
    def withings_config(self):
        """Get withings component config."""
        return self._withings_config

    @property
    def api_config(self):
        """Get api component config."""
        return self._api_config

    @property
    def http_config(self):
        """Get http component config."""
        return self._http_config

    @property
    def measures(self):
        """Get the measures."""
        return self._measures

    @property
    def hass_config(self):
        """Home assistant config."""
        return self._hass_config

    @property
    def throttle_interval(self):
        """Throttle interval."""
        return self._throttle_interval

    @property
    def nokia_request_response(self):
        """Request response."""
        return self._nokia_request_response

    @property
    def nokia_measures_response(self) -> nokia.NokiaMeasures:
        """Measures response."""
        return self._nokia_measures_response

    @property
    def nokia_sleep_response(self) -> nokia.NokiaSleep:
        """Sleep response."""
        return self._nokia_sleep_response

    @property
    def nokia_sleep_summary_response(self) -> nokia.NokiaSleepSummary:
        """Sleep summary response."""
        return self._nokia_sleep_summary_response


class WithingsFactoryData:
    """Data about the configured withing test component."""

    def __init__(
        self,
        hass,
        flow_id,
        nokia_auth_get_credentials_mock,
        nokia_api_request_mock,
        nokia_api_get_measures_mock,
        nokia_api_get_sleep_mock,
        nokia_api_get_sleep_summary_mock,
        data_manager_get_throttle_interval_mock,
    ):
        """Constructor."""
        self._hass = hass
        self._flow_id = flow_id
        self._nokia_auth_get_credentials_mock = nokia_auth_get_credentials_mock
        self._nokia_api_request_mock = nokia_api_request_mock
        self._nokia_api_get_measures_mock = nokia_api_get_measures_mock
        self._nokia_api_get_sleep_mock = nokia_api_get_sleep_mock
        self._nokia_api_get_sleep_summary_mock = nokia_api_get_sleep_summary_mock
        self._data_manager_get_throttle_interval_mock = (
            data_manager_get_throttle_interval_mock
        )

    @property
    def hass(self):
        """Get hass instance."""
        return self._hass

    @property
    def flow_id(self):
        """Get flow id."""
        return self._flow_id

    @property
    def nokia_auth_get_credentials_mock(self):
        """Get auth credentials mock."""
        return self._nokia_auth_get_credentials_mock

    @property
    def nokia_api_request_mock(self):
        """Get request mock."""
        return self._nokia_api_request_mock

    @property
    def nokia_api_get_measures_mock(self):
        """Get measures mock."""
        return self._nokia_api_get_measures_mock

    @property
    def nokia_api_get_sleep_mock(self):
        """Get sleep mock."""
        return self._nokia_api_get_sleep_mock

    @property
    def nokia_api_get_sleep_summary_mock(self):
        """Get sleep summary mock."""
        return self._nokia_api_get_sleep_summary_mock

    @property
    def data_manager_get_throttle_interval_mock(self):
        """Get throttle mock."""
        return self._data_manager_get_throttle_interval_mock

    async def configure_user(self):
        """Present a form with user profiles."""
        step = await self.hass.config_entries.flow.async_configure(self.flow_id, None)
        assert step["step_id"] == "user"

    async def configure_profile(self, profile: str):
        """Select the user profile. Present a form with authorization link."""
        print("CONFIG_PROFILE:", profile)
        step = await self.hass.config_entries.flow.async_configure(
            self.flow_id, {const.PROFILE: profile}
        )
        assert step["step_id"] == "auth"

    async def configure_code(self, profile: str, code: str):
        """Handle authorization code. Create config entries."""
        step = await self.hass.config_entries.flow.async_configure(
            self.flow_id, {const.PROFILE: profile, const.CODE: code}
        )
        assert step["type"] == "external_done"

        await self.hass.async_block_till_done()

        step = await self.hass.config_entries.flow.async_configure(
            self.flow_id, {const.PROFILE: profile, const.CODE: code}
        )

        assert step["type"] == "create_entry"

        await self.hass.async_block_till_done()

    async def configure_all(self, profile: str, code: str):
        """Configure all flow steps."""
        await self.configure_user()
        await self.configure_profile(profile)
        await self.configure_code(profile, code)


WithingsFactory = Callable[[WithingsFactoryConfig], Awaitable[WithingsFactoryData]]


@pytest.fixture(name="withings_factory")
def withings_factory_fixture(request, hass) -> WithingsFactory:
    """Home assistant platform fixture."""
    patches = []

    async def factory(config: WithingsFactoryConfig) -> WithingsFactoryData:
        CONFIG_SCHEMA(config.hass_config.get(DOMAIN))

        await async_process_ha_core_config(
            hass, config.hass_config.get("homeassistant")
        )
        assert await async_setup_component(hass, http.DOMAIN, config.hass_config)
        assert await async_setup_component(hass, api.DOMAIN, config.hass_config)

        nokia_auth_get_credentials_patch = asynctest.patch(
            "nokia.NokiaAuth.get_credentials",
            return_value=nokia.NokiaCredentials(
                access_token="my_access_token",
                token_expiry=time.time() + 600,
                token_type="my_token_type",
                refresh_token="my_refresh_token",
                user_id="my_user_id",
                client_id=config.withings_config.get(const.CLIENT_ID),
                consumer_secret=config.withings_config.get(const.CLIENT_SECRET),
            ),
        )
        nokia_auth_get_credentials_mock = nokia_auth_get_credentials_patch.start()

        nokia_api_request_patch = asynctest.patch(
            "nokia.NokiaApi.request", return_value=config.nokia_request_response
        )
        nokia_api_request_mock = nokia_api_request_patch.start()

        nokia_api_get_measures_patch = asynctest.patch(
            "nokia.NokiaApi.get_measures", return_value=config.nokia_measures_response
        )
        nokia_api_get_measures_mock = nokia_api_get_measures_patch.start()

        nokia_api_get_sleep_patch = asynctest.patch(
            "nokia.NokiaApi.get_sleep", return_value=config.nokia_sleep_response
        )
        nokia_api_get_sleep_mock = nokia_api_get_sleep_patch.start()

        nokia_api_get_sleep_summary_patch = asynctest.patch(
            "nokia.NokiaApi.get_sleep_summary",
            return_value=config.nokia_sleep_summary_response,
        )
        nokia_api_get_sleep_summary_mock = nokia_api_get_sleep_summary_patch.start()

        data_manager_get_throttle_interval_patch = asynctest.patch(
            "homeassistant.components.withings.common.WithingsDataManager"
            ".get_throttle_interval",
            return_value=config.throttle_interval,
        )
        data_manager_get_throttle_interval_mock = (
            data_manager_get_throttle_interval_patch.start()
        )

        get_measures_patch = asynctest.patch(
            "homeassistant.components.withings.sensor.get_measures",
            return_value=config.measures,
        )
        get_measures_patch.start()

        patches.extend(
            [
                nokia_auth_get_credentials_patch,
                nokia_api_request_patch,
                nokia_api_get_measures_patch,
                nokia_api_get_sleep_patch,
                nokia_api_get_sleep_summary_patch,
                data_manager_get_throttle_interval_patch,
                get_measures_patch,
            ]
        )

        # Collect the flow id.
        tasks = []

        orig_async_create_task = hass.async_create_task

        def create_task(*args):
            task = orig_async_create_task(*args)
            tasks.append(task)
            return task

        async_create_task_patch = asynctest.patch.object(
            hass, "async_create_task", side_effect=create_task
        )

        with async_create_task_patch:
            assert await async_setup_component(hass, DOMAIN, config.hass_config)
            await hass.async_block_till_done()

            flow_id = tasks[2].result()["flow_id"]

        return WithingsFactoryData(
            hass,
            flow_id,
            nokia_auth_get_credentials_mock,
            nokia_api_request_mock,
            nokia_api_get_measures_mock,
            nokia_api_get_sleep_mock,
            nokia_api_get_sleep_summary_mock,
            data_manager_get_throttle_interval_mock,
        )

    def cleanup():
        for patch in patches:
            patch.stop()

    request.addfinalizer(cleanup)

    return factory

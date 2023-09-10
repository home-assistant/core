"""Fixtures for tests."""
from collections.abc import Awaitable, Callable, Coroutine
import time
from typing import Any
from unittest.mock import patch

import arrow
import pytest
from withings_api.common import (
    GetSleepSummaryData,
    GetSleepSummarySerie,
    MeasureGetMeasGroup,
    MeasureGetMeasGroupAttrib,
    MeasureGetMeasGroupCategory,
    MeasureGetMeasMeasure,
    MeasureGetMeasResponse,
    MeasureType,
    SleepGetSummaryResponse,
    SleepModel,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.withings.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MockWithings
from .common import ComponentFactory, new_profile_config

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

ComponentSetup = Callable[[], Awaitable[MockWithings]]

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SCOPES = [
    "user.info",
    "user.metrics",
    "user.activity",
    "user.sleepevents",
]
TITLE = "henk"
WEBHOOK_ID = "55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"

PERSON0 = new_profile_config(
    profile="12345",
    user_id=12345,
    api_response_measure_get_meas=MeasureGetMeasResponse(
        measuregrps=(
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow().shift(hours=-1),
                date=arrow.utcnow().shift(hours=-1),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=70),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=5
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=60
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=50
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=10),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=2),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=20
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=70
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=70
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=100
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=60
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=95),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=95
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=100
                    ),
                ),
            ),
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow().shift(hours=-2),
                date=arrow.utcnow().shift(hours=-2),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=71),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=11),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=21),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=21
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=101
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=96),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=96
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=101
                    ),
                ),
            ),
            MeasureGetMeasGroup(
                attrib=MeasureGetMeasGroupAttrib.DEVICE_ENTRY_FOR_USER_AMBIGUOUS,
                category=MeasureGetMeasGroupCategory.REAL,
                created=arrow.utcnow(),
                date=arrow.utcnow(),
                deviceid="DEV_ID",
                grpid=1,
                measures=(
                    MeasureGetMeasMeasure(type=MeasureType.WEIGHT, unit=0, value=71),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_MASS_WEIGHT, unit=0, value=4
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_FREE_MASS, unit=0, value=40
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.MUSCLE_MASS, unit=0, value=51
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.BONE_MASS, unit=0, value=11),
                    MeasureGetMeasMeasure(type=MeasureType.HEIGHT, unit=0, value=201),
                    MeasureGetMeasMeasure(
                        type=MeasureType.TEMPERATURE, unit=0, value=41
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.BODY_TEMPERATURE, unit=0, value=34
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SKIN_TEMPERATURE, unit=0, value=21
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.FAT_RATIO, unit=-3, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.DIASTOLIC_BLOOD_PRESSURE, unit=0, value=71
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.SYSTOLIC_BLOOD_PRESSURE, unit=0, value=101
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HEART_RATE, unit=0, value=61
                    ),
                    MeasureGetMeasMeasure(type=MeasureType.SP02, unit=-2, value=98),
                    MeasureGetMeasMeasure(
                        type=MeasureType.HYDRATION, unit=-2, value=96
                    ),
                    MeasureGetMeasMeasure(
                        type=MeasureType.PULSE_WAVE_VELOCITY, unit=0, value=102
                    ),
                ),
            ),
        ),
        more=False,
        timezone=dt_util.UTC,
        updatetime=arrow.get("2019-08-01"),
        offset=0,
    ),
    api_response_sleep_get_summary=SleepGetSummaryResponse(
        more=False,
        offset=0,
        series=(
            GetSleepSummarySerie(
                timezone=dt_util.UTC,
                model=SleepModel.SLEEP_MONITOR,
                startdate=arrow.get("2019-02-01"),
                enddate=arrow.get("2019-02-01"),
                date=arrow.get("2019-02-01"),
                modified=arrow.get(12345),
                data=GetSleepSummaryData(
                    breathing_disturbances_intensity=110,
                    deepsleepduration=111,
                    durationtosleep=112,
                    durationtowakeup=113,
                    hr_average=114,
                    hr_max=115,
                    hr_min=116,
                    lightsleepduration=117,
                    remsleepduration=118,
                    rr_average=119,
                    rr_max=120,
                    rr_min=121,
                    sleep_score=122,
                    snoring=123,
                    snoringepisodecount=124,
                    wakeupcount=125,
                    wakeupduration=126,
                ),
            ),
            GetSleepSummarySerie(
                timezone=dt_util.UTC,
                model=SleepModel.SLEEP_MONITOR,
                startdate=arrow.get("2019-02-01"),
                enddate=arrow.get("2019-02-01"),
                date=arrow.get("2019-02-01"),
                modified=arrow.get(12345),
                data=GetSleepSummaryData(
                    breathing_disturbances_intensity=210,
                    deepsleepduration=211,
                    durationtosleep=212,
                    durationtowakeup=213,
                    hr_average=214,
                    hr_max=215,
                    hr_min=216,
                    lightsleepduration=217,
                    remsleepduration=218,
                    rr_average=219,
                    rr_max=220,
                    rr_min=221,
                    sleep_score=222,
                    snoring=223,
                    snoringepisodecount=224,
                    wakeupcount=225,
                    wakeupduration=226,
                ),
            ),
        ),
    ),
)


@pytest.fixture
def component_factory(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
):
    """Return a factory for initializing the withings component."""
    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi"
    ) as api_class_mock:
        yield ComponentFactory(
            hass, api_class_mock, hass_client_no_auth, aioclient_mock
        )


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id="12345",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": "12345",
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "use_webhook": True,
            "webhook_id": WEBHOOK_ID,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, MockWithings]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    async def func() -> MockWithings:
        mock = MockWithings(PERSON0)
        with patch(
            "homeassistant.components.withings.common.ConfigEntryWithingsApi",
            return_value=mock,
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func

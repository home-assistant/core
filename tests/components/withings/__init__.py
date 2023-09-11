"""Tests for the withings component."""
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import arrow
from withings_api import DateType
from withings_api.common import (
    GetSleepSummaryField,
    MeasureGetMeasGroupCategory,
    MeasureGetMeasResponse,
    MeasureType,
    NotifyAppli,
    NotifyListResponse,
    SleepGetSummaryResponse,
    UserGetDeviceResponse,
)

from homeassistant.components.webhook import async_generate_url
from homeassistant.core import HomeAssistant

from .common import WebhookResponse

from tests.common import load_json_object_fixture


async def call_webhook(
    hass: HomeAssistant, webhook_id: str, data: dict[str, Any], client
) -> WebhookResponse:
    """Call the webhook."""
    webhook_url = async_generate_url(hass, webhook_id)

    resp = await client.post(
        urlparse(webhook_url).path,
        data=data,
    )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data: dict[str, Any] = await resp.json()
    resp.close()

    return WebhookResponse(message=data["message"], message_code=data["code"])


class MockWithings:
    """Mock object for Withings."""

    def __init__(
        self,
        device_fixture: str = "person0_get_device.json",
        measurement_fixture: str = "person0_get_meas.json",
        sleep_fixture: str = "person0_get_sleep.json",
        notify_list_fixture: str = "person0_notify_list.json",
    ):
        """Initialize mock."""
        self.device_fixture = device_fixture
        self.measurement_fixture = measurement_fixture
        self.sleep_fixture = sleep_fixture
        self.notify_list_fixture = notify_list_fixture

    def user_get_device(self) -> UserGetDeviceResponse:
        """Get devices."""
        fixture = load_json_object_fixture(f"withings/{self.device_fixture}")
        return UserGetDeviceResponse(**fixture)

    def measure_get_meas(
        self,
        meastype: MeasureType | None = None,
        category: MeasureGetMeasGroupCategory | None = None,
        startdate: DateType | None = None,
        enddate: DateType | None = None,
        offset: int | None = None,
        lastupdate: DateType | None = None,
    ) -> MeasureGetMeasResponse:
        """Get measurements."""
        fixture = load_json_object_fixture(f"withings/{self.measurement_fixture}")
        return MeasureGetMeasResponse(**fixture)

    def sleep_get_summary(
        self,
        data_fields: Iterable[GetSleepSummaryField],
        startdateymd: DateType | None = arrow.utcnow(),
        enddateymd: DateType | None = arrow.utcnow(),
        offset: int | None = None,
        lastupdate: DateType | None = arrow.utcnow(),
    ) -> SleepGetSummaryResponse:
        """Get sleep."""
        fixture = load_json_object_fixture(f"withings/{self.sleep_fixture}")
        return SleepGetSummaryResponse(**fixture)

    def notify_list(
        self,
        appli: NotifyAppli | None = None,
    ) -> NotifyListResponse:
        """Get sleep."""
        fixture = load_json_object_fixture(f"withings/{self.notify_list_fixture}")
        return NotifyListResponse(**fixture)

"""Tests for the withings component."""
from collections.abc import Iterable
from typing import Any, Optional
from urllib.parse import urlparse

import arrow
from withings_api import DateType
from withings_api.common import (
    GetSleepSummaryField,
    MeasureGetMeasGroupCategory,
    MeasureGetMeasResponse,
    MeasureType,
    SleepGetSummaryResponse,
    UserGetDeviceResponse,
)

from homeassistant.components.webhook import async_generate_url
from homeassistant.core import HomeAssistant

from .common import ProfileConfig, WebhookResponse


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

    def __init__(self, user_profile: ProfileConfig):
        """Initialize mock."""
        self.api_response_user_get_device = user_profile.api_response_user_get_device
        self.api_response_measure_get_meas = user_profile.api_response_measure_get_meas
        self.api_response_sleep_get_summary = (
            user_profile.api_response_sleep_get_summary
        )

    def user_get_device(self) -> UserGetDeviceResponse:
        """Get devices."""
        if isinstance(self.api_response_user_get_device, Exception):
            raise self.api_response_user_get_device
        return self.api_response_user_get_device

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
        if isinstance(self.api_response_measure_get_meas, Exception):
            raise self.api_response_measure_get_meas
        return self.api_response_measure_get_meas

    def sleep_get_summary(
        self,
        data_fields: Iterable[GetSleepSummaryField],
        startdateymd: Optional[DateType] = arrow.utcnow(),
        enddateymd: Optional[DateType] = arrow.utcnow(),
        offset: Optional[int] = None,
        lastupdate: Optional[DateType] = arrow.utcnow(),
    ) -> SleepGetSummaryResponse:
        """Get sleep."""
        if isinstance(self.api_response_sleep_get_summary, Exception):
            raise self.api_response_sleep_get_summary
        return self.api_response_sleep_get_summary

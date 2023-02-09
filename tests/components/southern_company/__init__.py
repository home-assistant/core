"""Tests for the Southern Company integration."""
import datetime
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from southern_company_api.account import HourlyEnergyUsage, MonthlyUsage

from homeassistant.components.southern_company import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed

MONTH_DATA = MonthlyUsage(
    dollars_to_date=1.0,
    total_kwh_used=2.0,
    average_daily_usage=3.0,
    average_daily_cost=4.0,
    projected_usage_low=5.0,
    projected_usage_high=6.0,
    projected_bill_amount_low=7.0,
    projected_bill_amount_high=8.0,
)

HOURLY_DATA = [
    HourlyEnergyUsage(
        datetime.datetime(
            2023,
            1,
            1,
            1,
            0,
            0,
            0,
            datetime.timezone(datetime.timedelta(hours=-5), "EST"),
        ),
        usage=1.0,
        cost=2.0,
        temp=3.0,
    ),
    HourlyEnergyUsage(
        datetime.datetime(
            2023,
            1,
            1,
            2,
            0,
            0,
            0,
            datetime.timezone(datetime.timedelta(hours=-5), "EST"),
        ),
        usage=2.0,
        cost=3.0,
        temp=4.0,
    ),
]


def create_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Southern_Company",
        data={CONF_USERNAME: "sample_user", CONF_PASSWORD: "sample_pass"},
    )
    entry.add_to_hass(hass)
    return entry


async def async_init_integration(
    hass: HomeAssistant,
    error: str | None = None,
) -> ConfigEntry:
    """Set up the Southern Company integration in Home Assistant."""
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI"
    ) as api_mock:
        account_mock = AsyncMock()
        account_mock.number = "1"
        account_mock.get_month_data.return_value = MONTH_DATA
        account_mock.get_hourly_data.return_value = HOURLY_DATA
        api_mock.return_value.accounts = [account_mock]
        api_mock.return_value.get_accounts = AsyncMock()
        api_mock.return_value.get_accounts.return_value = [account_mock]

        api_mock.return_value.authenticate = AsyncMock()
        api_mock.return_value.authenticate.return_value = True
        api_mock.return_value.get_jwt = AsyncMock()
        api_mock.return_value.get_jwt.return_value = "sample_jwt"

        entry = create_entry(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt.utcnow() + timedelta(minutes=61))
        await hass.async_block_till_done()

        return entry

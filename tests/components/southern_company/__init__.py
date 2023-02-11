"""Tests for the Southern Company integration."""
import datetime
from unittest.mock import patch

from southern_company_api.account import Account, HourlyEnergyUsage, MonthlyUsage

from homeassistant.components.southern_company import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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

HOURLY_DATA_MISSING = [
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
        usage=None,
        cost=3.0,
        temp=4.0,
    ),
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
        cost=None,
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
        title="Southern Company",
        data={CONF_USERNAME: "sample_user", CONF_PASSWORD: "sample_pass"},
    )
    entry.add_to_hass(hass)
    return entry


class MockedAccount:
    """Mock Southern Company account."""

    def __init__(
        self,
        name: str,
        number: str,
        month_data: list[MonthlyUsage],
        hourly_data: list[HourlyEnergyUsage],
    ) -> None:
        """Mock a account object."""
        self.name = name
        self.number = number
        self.month_data = month_data
        self.hourly_data = hourly_data

    async def get_month_data(self, jwt: str) -> list[MonthlyUsage]:
        """Mock get month data of account."""
        return self.month_data

    async def get_hourly_data(
        self, jwt: str, time: datetime.datetime, end_time: datetime.datetime
    ) -> list[HourlyEnergyUsage]:
        """Mock get hourly data of account."""
        return self.hourly_data


class MockedApi:
    """Mock SouthernCompanyAPI."""

    def __init__(self, jwt, accounts) -> None:
        """Create a mocked version of the api."""
        self._jwt = jwt
        self._accounts = accounts

    @property
    async def jwt(self):
        """Get jwt of api."""
        return self._jwt

    @property
    async def accounts(self):
        """Get account of api."""
        return self._accounts

    async def get_accounts(self) -> MockedAccount | Account:
        """Get account of api."""
        return self._accounts

    async def authenticate(self) -> bool:
        """Authenticate api."""
        return True

    async def get_jwt(self) -> str:
        """Get jwt of api."""
        return self._jwt


async def async_init_integration(
    hass: HomeAssistant,
    hourly_data: list[HourlyEnergyUsage] = HOURLY_DATA,
    skip_setup: bool = False,
    jwt: str | None = "sample_jwt",
) -> ConfigEntry:
    """Set up the Southern Company integration in Home Assistant."""
    with patch(
        "homeassistant.components.southern_company.SouthernCompanyAPI"
    ) as api_mock:
        account_mock = MockedAccount("test_account", "1", MONTH_DATA, hourly_data)
        api_mock.return_value = MockedApi(jwt, [account_mock])
        entry = create_entry(hass)
        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        return entry

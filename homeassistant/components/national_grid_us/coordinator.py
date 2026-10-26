"""DataUpdateCoordinator for the National Grid US integration."""

from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import override

from py_nationalgrid import NationalGridClient, NationalGridConfig, create_cookie_jar
from py_nationalgrid.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridError,
    RetryExhaustedError,
)
from py_nationalgrid.models import BillingAccount, EnergyUsageCost, Meter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_ACCOUNT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

type NationalGridConfigEntry = ConfigEntry[NationalGridDataUpdateCoordinator]

# How far back to request AMI usage; the latest daily reading is the one used.
_USAGE_LOOKBACK = timedelta(days=30)


@dataclass
class MeterData:
    """Data for a single meter."""

    meter: Meter
    account_id: str
    billing_account: BillingAccount
    latest_usage: float | None = None
    latest_cost: float | None = None


@dataclass
class NationalGridCoordinatorData:
    """Data returned by the coordinator."""

    accounts: dict[str, BillingAccount]
    meters: dict[str, MeterData]
    costs: dict[str, list[EnergyUsageCost]]


class NationalGridDataUpdateCoordinator(
    DataUpdateCoordinator[NationalGridCoordinatorData]
):
    """Manage fetching data from the National Grid API."""

    config_entry: NationalGridConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NationalGridConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        session = async_create_clientsession(hass, cookie_jar=create_cookie_jar())
        self.api = NationalGridClient(
            config=NationalGridConfig(
                username=config_entry.data[CONF_USERNAME],
                password=config_entry.data[CONF_PASSWORD],
            ),
            session=session,
        )

    @override
    async def _async_update_data(self) -> NationalGridCoordinatorData:
        """Fetch data from the API."""
        account_id: str = self.config_entry.data[CONF_ACCOUNT_ID]

        today = dt_util.utcnow().date()

        try:
            data = await self._fetch_account_data(account_id, today)
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        except (
            CannotConnectError,
            RetryExhaustedError,
            NationalGridError,
            ValueError,
        ) as err:
            raise UpdateFailed(
                f"Failed to fetch data for account {account_id}: {err}"
            ) from err

        self._cache_computed_values(data)
        return data

    async def _fetch_account_data(
        self,
        account_id: str,
        today: date,
    ) -> NationalGridCoordinatorData:
        """Fetch data for a single account."""
        billing_account = await self.api.get_billing_account(account_id)
        premise_number = billing_account["premiseNumber"]

        meters: dict[str, MeterData] = {}
        for meter in billing_account["meter"]["nodes"]:
            service_point = str(meter["servicePointNumber"])
            # Accounts may reuse the same service point number, so key by a
            # composite of account_id and service point to avoid collisions.
            meter_key = f"{account_id}_{service_point}"
            meters[meter_key] = MeterData(
                meter=meter,
                account_id=account_id,
                billing_account=billing_account,
                latest_usage=await self._fetch_meter_usage(
                    meter, premise_number, today
                ),
            )

        region = billing_account["region"]
        if region:
            try:
                costs = await self.api.get_energy_usage_costs(
                    account_number=account_id,
                    query_date=today,
                    company_code=region,
                )
            except (
                CannotConnectError,
                RetryExhaustedError,
                NationalGridError,
                ValueError,
            ) as err:
                _LOGGER.debug(
                    "Could not fetch costs for account %s: %s", account_id, err
                )
                costs = []
        else:
            costs = []

        return NationalGridCoordinatorData(
            accounts={account_id: billing_account},
            meters=meters,
            costs={account_id: costs},
        )

    async def _fetch_meter_usage(
        self,
        meter: Meter,
        premise_number: int | str,
        today: date,
    ) -> float | None:
        """Fetch the latest daily AMI usage for a single meter.

        Non-AMI meters have no usage to report. Per-meter failures degrade to
        no reading rather than failing the whole account refresh.
        """
        if not meter["hasAmiSmartMeter"]:
            return None

        try:
            usages = await self.api.get_ami_energy_usages(
                meter_number=meter["meterNumber"],
                premise_number=premise_number,
                service_point_number=meter["servicePointNumber"],
                meter_point_number=meter["meterPointNumber"],
                date_from=today - _USAGE_LOOKBACK,
                date_to=today,
                fuel_type=meter["fuelType"].upper(),
            )
        except (
            CannotConnectError,
            RetryExhaustedError,
            NationalGridError,
            ValueError,
        ) as err:
            _LOGGER.debug(
                "Could not fetch usage for meter %s: %s", meter["meterNumber"], err
            )
            return None

        if not usages:
            return None
        return max(usages, key=lambda u: u["date"])["quantity"]

    def _cache_computed_values(self, data: NationalGridCoordinatorData) -> None:
        """Pre-compute the latest cost for each meter."""
        for meter_data in data.meters.values():
            fuel_type = meter_data.meter["fuelType"].upper()
            cost = self._find_latest_cost(
                data.costs.get(meter_data.account_id, []), fuel_type
            )
            meter_data.latest_cost = cost["amount"] if cost else None

    @staticmethod
    def _find_latest_cost(
        costs: list[EnergyUsageCost], fuel_type: str
    ) -> EnergyUsageCost | None:
        """Find the most recent cost entry for a fuel type."""
        filtered = [c for c in costs if c["fuelType"] == fuel_type]
        if not filtered:
            return None
        # "month" is 1-12 only (not year-aware), so sorting by it returns the
        # previous year's December over a more recent January. The "date" field
        # is in YYYY-MM-DD format and sorts correctly across year boundaries.
        return max(filtered, key=lambda c: c["date"])

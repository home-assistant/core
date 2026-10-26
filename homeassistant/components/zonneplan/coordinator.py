"""Coordinator for Zonneplan."""

from abc import abstractmethod
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING, override

from pyzonneplan import (
    Account,
    Battery,
    BatteryControlMode,
    ChargePoint,
    Connection,
    ConsumerPrices,
    ElectricityChart,
    GasChart,
    Zonneplan,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanError,
    ZonneplanRateLimitError,
    ZonneplanTimeoutError,
)
from pyzonneplan.const import BatteryMode, ConsumptionChart, PriceChart

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=15)
BATTERY_UPDATE_INTERVAL = timedelta(minutes=5)
BATTERY_CONTROL_UPDATE_INTERVAL = timedelta(minutes=5)
CHARGE_POINT_UPDATE_INTERVAL = timedelta(minutes=1)

type ZonneplanConfigEntry = ConfigEntry[ZonneplanRuntimeData]


@dataclass(frozen=True, kw_only=True)
class ZonneplanRuntimeData:
    """Runtime data of a Zonneplan config entry."""

    coordinator: ZonneplanCoordinator
    battery_coordinator: ZonneplanBatteryCoordinator
    battery_control_coordinator: ZonneplanBatteryControlCoordinator
    charge_point_coordinator: ZonneplanChargePointCoordinator


@dataclass(frozen=True, kw_only=True)
class ZonneplanData:
    """Data fetched by the Zonneplan coordinator."""

    account: Account
    electricity_prices: ConsumerPrices | None = None
    gas_prices: ConsumerPrices | None = None
    electricity_usage: ElectricityChart | None = None
    gas_usage: GasChart | None = None


@dataclass(frozen=True, kw_only=True)
class ZonneplanBatteryData:
    """Data of a Zonneplan home battery."""

    battery: Battery
    day_start: datetime | None


def _connection(account: Account, market_segment: str) -> Connection | None:
    """Return the first connection of a market segment, if the account has one."""
    return next(
        (
            connection
            for connection in account.connections
            if connection.market_segment is not None
            and market_segment in connection.market_segment
        ),
        None,
    )


class ZonneplanBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator for the Zonneplan API."""

    config_entry: ZonneplanConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZonneplanConfigEntry,
        zonneplan: Zonneplan,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.zonneplan = zonneplan

    @abstractmethod
    async def _async_fetch(self) -> _DataT:
        """Fetch the data from the Zonneplan API."""

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch data from the Zonneplan API."""
        try:
            data = await self._async_fetch()
        except ZonneplanAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ZonneplanTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except ZonneplanConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except ZonneplanRateLimitError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                retry_after=err.retry_after,
            ) from err
        except ZonneplanError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

        if TYPE_CHECKING:
            assert self.zonneplan.token is not None

        token = self.zonneplan.token.as_dict()
        if self.config_entry.data.get(CONF_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )

        return data


class ZonneplanCoordinator(ZonneplanBaseCoordinator[ZonneplanData]):
    """Coordinator to manage fetching Zonneplan account data."""

    def __init__(
        self, hass: HomeAssistant, entry: ZonneplanConfigEntry, zonneplan: Zonneplan
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, zonneplan, UPDATE_INTERVAL)

    async def _async_fetch_electricity(
        self, account: Account, today: date
    ) -> tuple[ConsumerPrices | None, ElectricityChart | None]:
        """Fetch electricity prices and usage, if the account has electricity."""
        if (connection := _connection(account, "electricity")) is None:
            return None, None
        return await asyncio.gather(
            self.zonneplan.async_get_consumer_prices(PriceChart.ELECTRICITY_HOURLY),
            self.zonneplan.async_get_electricity_chart(
                connection.uuid, today, ConsumptionChart.DAYS
            ),
        )

    async def _async_fetch_gas(
        self, account: Account, today: date
    ) -> tuple[ConsumerPrices | None, GasChart | None]:
        """Fetch gas prices and usage, if the account has gas."""
        if (connection := _connection(account, "gas")) is None:
            return None, None
        return await asyncio.gather(
            self.zonneplan.async_get_consumer_prices(PriceChart.GAS_DAILY),
            self.zonneplan.async_get_gas_chart(
                connection.uuid, today, ConsumptionChart.DAYS
            ),
        )

    @override
    async def _async_fetch(self) -> ZonneplanData:
        """Fetch the account, prices and usage."""
        account = await self.zonneplan.async_get_account()
        # The consumption charts cover the month of the given local day.
        today = dt_util.now().date()
        (
            (electricity_prices, electricity_usage),
            (gas_prices, gas_usage),
        ) = await asyncio.gather(
            self._async_fetch_electricity(account, today),
            self._async_fetch_gas(account, today),
        )
        return ZonneplanData(
            account=account,
            electricity_prices=electricity_prices,
            gas_prices=gas_prices,
            electricity_usage=electricity_usage,
            gas_usage=gas_usage,
        )


class ZonneplanBatteryCoordinator(
    ZonneplanBaseCoordinator[dict[str, ZonneplanBatteryData]]
):
    """Coordinator to manage fetching the Zonneplan home batteries."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZonneplanConfigEntry,
        zonneplan: Zonneplan,
        connection_uuids: dict[str, str],
    ) -> None:
        """Initialize the coordinator with the connection UUID of each battery."""
        super().__init__(hass, entry, zonneplan, BATTERY_UPDATE_INTERVAL)
        self.connection_uuids = connection_uuids

    @override
    async def _async_fetch(self) -> dict[str, ZonneplanBatteryData]:
        """Fetch the state of every battery, keyed by contract UUID."""
        installations = await asyncio.gather(
            *(
                self.zonneplan.async_get_battery(connection_uuid, contract_uuid)
                for contract_uuid, connection_uuid in self.connection_uuids.items()
            )
        )
        batteries: dict[str, ZonneplanBatteryData] = {}
        for contract_uuid, installation in zip(
            self.connection_uuids, installations, strict=True
        ):
            if (battery := installation.battery) is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="battery_not_found",
                )
            batteries[contract_uuid] = ZonneplanBatteryData(
                battery=battery,
                day_start=(
                    installation.measurement_groups[0].date
                    if installation.measurement_groups
                    else None
                ),
            )
        return batteries


class ZonneplanChargePointCoordinator(ZonneplanBaseCoordinator[dict[str, ChargePoint]]):
    """Coordinator to manage fetching the Zonneplan charge points."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZonneplanConfigEntry,
        zonneplan: Zonneplan,
        connection_uuids: dict[str, str],
    ) -> None:
        """Initialize the coordinator with the connection UUID of each charge point."""
        super().__init__(hass, entry, zonneplan, CHARGE_POINT_UPDATE_INTERVAL)
        self.connection_uuids = connection_uuids

    @override
    async def _async_fetch(self) -> dict[str, ChargePoint]:
        """Fetch the state of every charge point, keyed by contract UUID."""
        installations = await asyncio.gather(
            *(
                self.zonneplan.async_get_charge_point(connection_uuid, contract_uuid)
                for contract_uuid, connection_uuid in self.connection_uuids.items()
            )
        )
        charge_points: dict[str, ChargePoint] = {}
        for contract_uuid, installation in zip(
            self.connection_uuids, installations, strict=True
        ):
            if (charge_point := installation.charge_point) is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="charge_point_not_found",
                )
            charge_points[contract_uuid] = charge_point
        return charge_points


class ZonneplanBatteryControlCoordinator(
    ZonneplanBaseCoordinator[dict[str, BatteryControlMode]]
):
    """Coordinator to manage the control mode of the Zonneplan home batteries."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZonneplanConfigEntry,
        zonneplan: Zonneplan,
        connection_uuids: dict[str, str],
    ) -> None:
        """Initialize the coordinator with the connection UUID of each battery."""
        super().__init__(hass, entry, zonneplan, BATTERY_CONTROL_UPDATE_INTERVAL)
        self.connection_uuids = connection_uuids

    @override
    async def _async_fetch(self) -> dict[str, BatteryControlMode]:
        """Fetch the control mode of every battery, keyed by contract UUID."""
        control_modes = await asyncio.gather(
            *(
                self.zonneplan.async_get_battery_control_mode(contract_uuid)
                for contract_uuid in self.connection_uuids
            )
        )
        return dict(zip(self.connection_uuids, control_modes, strict=True))

    async def async_set_control_mode(
        self, contract_uuid: str, mode: BatteryMode
    ) -> None:
        """Switch a battery to another control mode and refresh the control data."""
        try:
            await self.zonneplan.async_set_battery_control_mode(
                self.connection_uuids[contract_uuid], contract_uuid, mode
            )
        except ValueError as err:
            # Raised when day-ahead arbitrage was never set up in the app.
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="day_ahead_arbitrage_not_set_up",
            ) from err
        except ZonneplanAuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ZonneplanTimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except ZonneplanConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except ZonneplanRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
            ) from err
        except ZonneplanError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err
        finally:
            # A failed switch can leave the battery half switched.
            await self.async_request_refresh()

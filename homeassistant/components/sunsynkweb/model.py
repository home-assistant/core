"""Top level data model for the sunsynk web api."""

from dataclasses import dataclass
import decimal
import logging
import pprint

from .const import BASE_API, BASE_HEADERS

_LOGGER = logging.getLogger(__name__)


@dataclass
class Plant:
    """Proxy for the 'Plant' object in sunsynk web api.

    A plant can host multiple inverters and other devices. Our plant object
    carries a summary of the data from all inverters in the plant.

    In the limited sample i've got, there is one plant per inverter.

    """

    id: int
    master_id: int
    name: str
    status: int
    battery_power: int = 0
    state_of_charge: float = 0
    load_power: int = 0
    grid_power: int = 0
    pv_power: int = 0
    inverter_sn: int | None = None
    acc_pv: decimal.Decimal = decimal.Decimal(0)
    acc_grid_export: decimal.Decimal = decimal.Decimal(0)
    acc_grid_import: decimal.Decimal = decimal.Decimal(0)
    acc_battery_discharge: decimal.Decimal = decimal.Decimal(0)
    acc_battery_charge: decimal.Decimal = decimal.Decimal(0)
    acc_load: decimal.Decimal = decimal.Decimal(0)

    def ismaster(self):
        """Is the plant a master plant.

         Unused at the moment, but required when introducing read-write calls
        (for instance to command to charge batteries from the grid).
        """
        return self.master_id == self.id

    @classmethod
    def from_api(cls, api_return):
        """Create the plant from the return of the web api."""
        return cls(
            name=api_return["name"],
            id=api_return["id"],
            master_id=api_return["masterId"],
            status=api_return["status"],
        )

    async def enrich_inverters(self, coordinator):
        """Populate inverters' serial numbers.

        The plant summary doesn't contain the inverters, so we have a separate call to populate inverter's serial numbers.
        """
        res = await coordinator.session.get(
            BASE_API + f"/plant/{self.id}/inverters",
            headers=self._headers(coordinator),
            params={"page": 1, "limit": 20, "type": -1, "status": -1},
        )
        returned = await res.json()
        assert len(returned["data"]["infos"]) == 1
        self.inverter_sn = returned["data"]["infos"][0]["sn"]

    async def _get_instantaneous_data(self, coordinator, headers):
        """Populate instantenous data.

        Instantenous data is convienently summarised in the 'flow' api end point.
        """
        res = await coordinator.session.get(
            BASE_API + f"/plant/energy/{self.id}/flow",
            headers=headers,
            params={"page": 1, "limit": 20},
        )
        returned = await res.json()
        if returned.get("msg") != "Success":
            # we only check for the bearer here as it's the first call of the refresh cycle
            _LOGGER.debug(
                "unexpected answer from sunsynk web api : %s", pprint.pformat(returned)
            )
            if returned["code"] == 401:  # bearer token expired
                coordinator.bearer = None  # will force refresh of token on next update
            return

        _LOGGER.debug("Flow Api returned %s", pprint.pformat(returned))

        self.battery_power = returned["data"]["battPower"]
        if returned["data"]["toBat"]:
            self.battery_power *= -1
        self.state_of_charge = returned["data"]["soc"]
        self.load_power = returned["data"]["loadOrEpsPower"]
        self.grid_power = returned["data"]["gridOrMeterPower"]
        if returned["data"]["toGrid"]:
            self.grid_power *= -1
        self.pv_power = returned["data"]["pvPower"]

    async def _get_total_grid(self, coordinator, headers):
        res = await coordinator.session.get(
            BASE_API + f"/inverter/grid/{self.inverter_sn}/realtime",
            headers=headers,
            params={"lan": "en"},
        )
        returned = await res.json()
        self.acc_grid_export = returned["data"]["etotalTo"]
        self.acc_grid_import = returned["data"]["etotalFrom"]

    async def _get_total_battery(self, coordinator, headers):
        res = await coordinator.session.get(
            BASE_API + f"/inverter/battery/{self.inverter_sn}/realtime",
            headers=headers,
            params={"lan": "en"},
        )
        returned = await res.json()
        self.acc_battery_charge = returned["data"]["etotalChg"]
        self.acc_battery_discharge = returned["data"]["etotalDischg"]

    async def _get_total_pv(self, coordinator, headers):
        res = await coordinator.session.get(
            BASE_API + f"/inverter/{self.inverter_sn}/total",
            headers=headers,
            params={"lan": "en"},
        )
        returned = await res.json()
        self.acc_pv = sum(
            [
                decimal.Decimal(i["value"])
                for i in returned["data"]["infos"][0]["records"]
            ]
        )

    async def _get_total_load(self, coordinator, headers):
        res = await coordinator.session.get(
            BASE_API + f"/inverter/load/{self.inverter_sn}/realtime",
            headers=headers,
            params={"lan": "en"},
        )
        returned = await res.json()
        self.acc_load = returned["data"]["totalUsed"]

    def _headers(self, coordinator):
        headers = BASE_HEADERS.copy()
        headers.update({"Authorization": f"Bearer{coordinator.bearer}"})
        return headers

    async def update(self, coordinator):
        """Update all sensors."""
        await self._get_instantaneous_data(coordinator, self._headers(coordinator))
        if coordinator.bearer is not None:
            # this assumes it's not going to expire between any of these calls
            # if it does, the update will raise but will restore service above
            await self._get_total_pv(coordinator, self._headers(coordinator))
            await self._get_total_grid(coordinator, self._headers(coordinator))
            await self._get_total_battery(coordinator, self._headers(coordinator))
            await self._get_total_load(coordinator, self._headers(coordinator))
        else:
            _LOGGER.debug("skipping updates, bearer will refresh next iteration")


@dataclass
class Installation:
    """An installation is a series of plants.

    This integration presents the plants as a single entity.
    """

    plants: list

    @classmethod
    def from_api(cls, api_return):
        """Create the installation from the sunsynk web api."""
        assert "data" in api_return
        assert api_return["msg"] == "Success"
        return cls(plants=[Plant.from_api(ret) for ret in api_return["data"]["infos"]])

    async def update(self, coordinator):
        """Update all the plants. They will in turn update their sensors."""
        for plant in self.plants:
            await plant.update(coordinator)


async def get_plants(coordinator):
    """Start walking the plant composition."""
    headers = BASE_HEADERS.copy()
    headers.update({"Authorization": f"Bearer{coordinator.bearer}"})
    returned = await coordinator.session.get(
        BASE_API + "/plants", headers=headers, params={"page": 1, "limit": 20}
    )
    returned = await returned.json()
    installation = Installation.from_api(returned)
    for plant in installation.plants:
        await plant.enrich_inverters(coordinator)
    return installation

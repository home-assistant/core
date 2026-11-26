"""Config flow for Spain fuel prices (Geoportal Gasolineras)."""

from typing import Any, override

from aioprecioscarburantes import PreciosCarburantes, PreciosCarburantesError, Station
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_MUNICIPALITY_ID,
    CONF_PROVINCE_ID,
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from .names import brand_name, clean_address, station_name


def _selector(options: list[SelectOptionDict]) -> SelectSelector:
    """Return a dropdown sorted by label."""
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(options, key=lambda option: option["label"]),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


class GeoportalGasolinerasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single config entry; stations are added as subentries."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types: fuel stations."""
        return {SUBENTRY_TYPE_STATION: StationSubentryFlow}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check the service can be reached and create the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = PreciosCarburantes(session=async_get_clientsession(self.hass))
            try:
                await client.get_provinces()
            except PreciosCarburantesError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Spain fuel prices", data={})
        return self.async_show_form(step_id="user", errors=errors)


class StationSubentryFlow(ConfigSubentryFlow):
    """Add a fuel station: province, municipality and station."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._province_id = ""
        self._municipality_id = ""
        self._stations: dict[str, Station] = {}

    @property
    def _client(self) -> PreciosCarburantes:
        return PreciosCarburantes(session=async_get_clientsession(self.hass))

    def _is_configured(self, station_id: str) -> bool:
        """Return if the station was already added."""
        return any(
            subentry.unique_id == station_id
            for subentry in self._get_entry().subentries.values()
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the province."""
        if user_input is not None:
            self._province_id = user_input[CONF_PROVINCE_ID]
            return await self.async_step_municipality()
        try:
            provinces = await self._client.get_provinces()
        except PreciosCarburantesError:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_PROVINCE_ID): _selector(
                        [
                            SelectOptionDict(
                                value=province.id, label=province.name.title()
                            )
                            for province in provinces
                        ]
                    )
                }
            ),
        )

    async def async_step_municipality(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the municipality."""
        if user_input is not None:
            self._municipality_id = user_input[CONF_MUNICIPALITY_ID]
            try:
                result = await self._client.get_stations_by_municipality(
                    self._municipality_id
                )
            except PreciosCarburantesError:
                return self.async_abort(reason="cannot_connect")
            self._stations = {
                station.id: station
                for station in result.stations
                if not self._is_configured(station.id)
            }
            if not self._stations:
                return self.async_abort(reason="no_stations")
            return await self.async_step_station()
        try:
            municipalities = await self._client.get_municipalities(self._province_id)
        except PreciosCarburantesError:
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="municipality",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_MUNICIPALITY_ID): _selector(
                        [
                            SelectOptionDict(
                                value=municipality.id, label=municipality.name
                            )
                            for municipality in municipalities
                        ]
                    )
                }
            ),
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the station."""
        if user_input is not None:
            station = self._stations[user_input[CONF_STATION_ID]]
            if self._is_configured(station.id):
                return self.async_abort(reason="already_configured")
            taken = {
                subentry.title for subentry in self._get_entry().subentries.values()
            }
            return self.async_create_entry(
                title=station_name(station, taken),
                data={
                    CONF_PROVINCE_ID: self._province_id,
                    CONF_MUNICIPALITY_ID: self._municipality_id,
                    CONF_STATION_ID: station.id,
                },
                unique_id=station.id,
            )
        labels = {
            station.id: f"{brand_name(station.brand)} – {clean_address(station.address)}"
            for station in self._stations.values()
        }
        repeated = {
            label for label in labels.values() if list(labels.values()).count(label) > 1
        }
        return self.async_show_form(
            step_id="station",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STATION_ID): _selector(
                        [
                            SelectOptionDict(
                                value=station_id,
                                label=(
                                    f"{label} (#{station_id})"
                                    if label in repeated
                                    else label
                                ),
                            )
                            for station_id, label in labels.items()
                        ]
                    )
                }
            ),
        )

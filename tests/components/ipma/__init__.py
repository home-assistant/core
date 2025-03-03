"""Tests for the IPMA component."""

from datetime import UTC, datetime

from pyipma.forecast import Forecast, Forecast_Location, Weather_Type
from pyipma.observation import Observation
from pyipma.rcm import RCM
from pyipma.uv import UV
from pyipma.warnings import Warning

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME

ENTRY_CONFIG = {
    CONF_NAME: "Home Town",
    CONF_LATITUDE: "1",
    CONF_LONGITUDE: "2",
    CONF_MODE: "hourly",
}


class MockLocation:
    """Mock Location from pyipma."""

    async def warnings(self, api):
        """Mock Warnings."""
        return [
            Warning(
                text="Na costa Sul, ondas de sueste com 2 a 2,5 metros, em especial "
                "no barlavento.",
                awarenessTypeName="Agitação Marítima",
                idAreaAviso="FAR",
                startTime=datetime(2024, 12, 26, 12, 24),
                awarenessLevelID="yellow",
                endTime=datetime(2024, 12, 28, 6, 0),
            )
        ]

    async def fire_risk(self, api):
        """Mock Fire Risk."""
        return RCM("some place", 3, (0, 0))

    async def uv_risk(self, api):
        """Mock UV Index."""
        return UV(0, "0", datetime(2020, 1, 16, 0, 0, 0), 0, 5.7)

    async def observation(self, api):
        """Mock Observation."""
        return Observation(
            precAcumulada=0.0,
            humidade=71.0,
            pressao=1000.0,
            radiacao=0.0,
            temperatura=18.0,
            idDireccVento=8,
            intensidadeVentoKM=3.94,
            intensidadeVento=1.0944,
            timestamp=datetime(2020, 1, 16, 0, 0, 0),
            idEstacao=0,
        )

    async def forecast(self, api, period):
        """Mock Forecast."""

        if period == 24:
            return [
                Forecast(
                    utci=None,
                    dataPrev=datetime(2020, 1, 16, 0, 0, 0),
                    idPeriodo=24,
                    hR=None,
                    tMax=16.2,
                    tMin=10.6,
                    probabilidadePrecipita=100.0,
                    tMed=13.4,
                    dataUpdate=datetime(2020, 1, 15, 7, 51, 0),
                    idTipoTempo=Weather_Type(9, "Rain/showers", "Chuva/aguaceiros"),
                    ddVento="S",
                    ffVento=10,
                    idFfxVento=0,
                    iUv=0,
                    intervaloHora="",
                    location=Forecast_Location(0, "", 0, 0, 0, "", (0, 0)),
                ),
            ]
        if period == 1:
            return [
                Forecast(
                    utci=7.7,
                    dataPrev=datetime(2020, 1, 15, 1, 0, 0, tzinfo=UTC),
                    idPeriodo=1,
                    hR=86.9,
                    tMax=12.0,
                    tMin=None,
                    probabilidadePrecipita=80.0,
                    tMed=10.6,
                    dataUpdate=datetime(2020, 1, 15, 2, 51, 0),
                    idTipoTempo=Weather_Type(
                        10, "Light rain", "Chuva fraca ou chuvisco"
                    ),
                    ddVento="S",
                    ffVento=32.7,
                    idFfxVento=0,
                    iUv=0,
                    intervaloHora="",
                    location=Forecast_Location(0, "", 0, 0, 0, "", (0, 0)),
                ),
                Forecast(
                    utci=5.7,
                    dataPrev=datetime(2020, 1, 15, 2, 0, 0, tzinfo=UTC),
                    idPeriodo=1,
                    hR=86.9,
                    tMax=12.0,
                    tMin=None,
                    probabilidadePrecipita=80.0,
                    tMed=10.6,
                    dataUpdate=datetime(2020, 1, 15, 2, 51, 0),
                    idTipoTempo=Weather_Type(1, "Clear sky", "C\u00e9u limpo"),
                    ddVento="S",
                    ffVento=32.7,
                    idFfxVento=0,
                    iUv=0,
                    intervaloHora="",
                    location=Forecast_Location(0, "", 0, 0, 0, "", (0, 0)),
                ),
            ]
        raise ValueError(f"Unknown forecast period: {period}")

    name = "HomeTown"
    station = "HomeTown Station"
    station_latitude = 0
    station_longitude = 0
    global_id_local = 1130600
    id_station = 1200545

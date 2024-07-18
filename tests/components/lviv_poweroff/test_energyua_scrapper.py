from pathlib import Path

from aioresponses import aioresponses
import pytest

from homeassistant.components.lviv_poweroff.energyua_scrapper import EnergyUaScrapper
from homeassistant.components.lviv_poweroff.entities import PowerOffPeriod


@pytest.fixture
def energyua_page():
    test_file = Path(__file__).parent / "energyua_page.html"

    with open(test_file, encoding="utf-8") as file:
        return file.read()


async def test_energyua_scrapper(energyua_page) -> None:
    # Given a response from the EnergyUa website
    with aioresponses() as mock:
        mock.get("https://lviv.energy-ua.info/grupa/1.1", body=energyua_page)
        # When scrapper is called for power-off periods
        scrapper = EnergyUaScrapper("1.1")
        poweroffs = await scrapper.get_power_off_periods()

    # Then the power-off periods are extracted correctly
    assert poweroffs is not None
    assert len(poweroffs) == 8
    assert poweroffs[0] == PowerOffPeriod(23, 0, today=True)
    assert poweroffs[1] == PowerOffPeriod(0, 2, today=True)
    assert poweroffs[2] == PowerOffPeriod(6, 8, today=True)
    assert poweroffs[3] == PowerOffPeriod(11, 14, today=True)
    assert poweroffs[4] == PowerOffPeriod(16, 20, today=True)
    assert poweroffs[5] == PowerOffPeriod(22, 0, today=True)
    assert poweroffs[6] == PowerOffPeriod(7, 9, today=False)
    assert poweroffs[7] == PowerOffPeriod(19, 21, today=False)

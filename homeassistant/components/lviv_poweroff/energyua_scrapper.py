"""Provides classes for scraping power off periods from the Energy UA website."""

import re

import aiohttp
from bs4 import BeautifulSoup

from .const import PowerOffGroup
from .entities import PowerOffPeriod

URL = "https://lviv.energy-ua.info/grupa/{}"
PATTERN = r"З (\d{2}):\d{2} до (\d{2}):\d{2}"


class EnergyUaScrapper:
    """Class for scraping power off periods from the Energy UA website."""

    def __init__(self, group: PowerOffGroup) -> None:
        """Initialize the EnergyUaScrapper object."""
        self.group = group

    async def validate(self) -> bool:
        async with (
            aiohttp.ClientSession() as session,
            session.get(URL.format(self.group)) as response,
        ):
            return response.status == 200

    async def get_power_off_periods(self) -> list[PowerOffPeriod]:
        async with (
            aiohttp.ClientSession() as session,
            session.get(URL.format(self.group)) as response,
        ):
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            results = []
            grafiks = soup.find_all("div", class_="grafik_string_list")
            grafiks_today = grafiks[0].find_all("div", class_="grafik_string_list_item")
            for item in grafiks_today:
                start, end = self._parse_item(item)
                results.append(PowerOffPeriod(start, end, today=True))
            graphiks_tomorrow = grafiks[1].find_all(
                "div", class_="grafik_string_list_item"
            )
            for item in graphiks_tomorrow:
                start, end = self._parse_item(item)
                results.append(PowerOffPeriod(start, end, today=False))
            return results

    def _parse_item(self, item: BeautifulSoup) -> tuple[int, int]:
        match = re.search(PATTERN, item.text)

        if match:
            # Extract start and end hours and convert them to integers
            start_hour = int(match.group(1))
            end_hour = int(match.group(2))

            return start_hour, end_hour
        else:
            raise ValueError(f"Time period not found in the input string: {item.text}")

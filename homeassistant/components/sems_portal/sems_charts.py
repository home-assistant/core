"""Used for getting sems charts data."""

from datetime import datetime
from typing import Any

from aiohttp import ClientSession


async def get_plant_power_chart(
    session: ClientSession, plant_id: str, token: str
) -> Any:
    """Retrieve powerplant chart data."""
    formatted_date = datetime.now().strftime("%Y-%m-%d")
    url = "https://au.semsportal.com/api/v2/Charts/GetPlantPowerChart"
    headers = {"Content-Type": "application/json", "Token": token}
    body = {"id": plant_id, "date": formatted_date, "full_script": False}

    response = await session.post(url, headers=headers, json=body, timeout=10000)
    response_data = response.json()

    return response_data

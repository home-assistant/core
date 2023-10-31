"""Used for getting powerflow data."""

from typing import Any

from aiohttp import ClientSession


async def get_powerflow(
    session: ClientSession, power_station_id: str, token: str
) -> Any:
    """Get the powerflow data."""

    url = "https://au.semsportal.com/api/v2/PowerStation/GetPowerflow"
    headers = {"Content-Type": "application/json", "Token": token}
    body = {"PowerStationId": power_station_id}

    response = await session.post(url, headers=headers, json=body)
    response_data = await response.json()

    return response_data["data"]

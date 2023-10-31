"""Used to get information about the plant."""

from typing import Any

from aiohttp import ClientSession


async def get_plantDetails(
    session: ClientSession, power_station_id: str, token: str
) -> Any:
    """Get powerplant details."""
    url = "https://au.semsportal.com/api/v3/PowerStation/GetPlantDetailByPowerstationId"
    headers = {"Content-Type": "application/json", "Token": token}
    body = {"PowerStationId": power_station_id}

    response = await session.post(url, headers=headers, json=body)
    response_data = await response.json()

    return response_data["data"]

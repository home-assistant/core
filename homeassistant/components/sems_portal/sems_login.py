"""Used for login logic."""

from typing import Any

from aiohttp import ClientSession


async def login_to_sems(session: ClientSession, account: str, pwd: str) -> Any:
    """Login to the SEMS portal."""
    url = "https://www.semsportal.com/api/v1/Common/CrossLogin"
    headers = {
        "Content-Type": "application/json",
        "Token": '{"version":"v2.1.0","client":"ios","language":"en"}',
    }
    body = {"account": account, "pwd": pwd}

    response = await session.post(url, headers=headers, json=body)
    response_data = await response.json()

    return response_data["data"]

"""Support for register Vulcan account."""

from typing import Any

from vulcan import Account, Keystore


async def register(token: str, symbol: str, pin: str) -> dict[str, Any]:
    """Register integration and save credentials."""
    keystore = await Keystore.create(device_model="Home Assistant")
    account = await Account.register(keystore, token, symbol, pin)
    return {"account": account, "keystore": keystore}

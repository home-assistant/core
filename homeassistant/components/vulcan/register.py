"""Support for register Vulcan account."""

from vulcan import Account, Keystore


async def register(hass, token, symbol, pin):
    """Register integration and save credentials."""
    keystore = await Keystore.create(device_model="Home Assistant")
    account = await Account.register(keystore, token, symbol, pin)
    return {"account": account, "keystore": keystore}

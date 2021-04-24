"""Support for register Vulcan account."""
from functools import partial
from pathlib import Path

from vulcan import Account, Keystore


async def register(hass, token, symbol, pin):
    """Register integration and save credentials."""
    Path(".vulcan").mkdir(parents=True, exist_ok=True)
    keystore = await hass.async_add_executor_job(
        partial(Keystore.create, device_model="Home Assistant")
    )
    account = await Account.register(keystore, token, symbol, pin)
    with open(f".vulcan/keystore-{account.user_login}.json", "w") as file:
        file.write(keystore.as_json)
    with open(f".vulcan/account-{account.user_login}.json", "w") as file:
        file.write(account.as_json)
    return {"account": account, "keystore": keystore}

"""Helpers for zwave_me config flow."""
from zwave_me_ws import ZWaveMe


async def get_uuid(url, token):
    """Get an uuid from Z-Wave-Me."""
    conn = ZWaveMe(url=url, token=token)
    uuid = None
    if await conn.get_connection():
        uuid = await conn.get_uuid()
    await conn.close_ws()
    return uuid

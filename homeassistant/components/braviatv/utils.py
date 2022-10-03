"""BraviaTV helpers functions."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id

from .const import NICKNAME


async def gen_instance_ids(hass: HomeAssistant) -> tuple[str, str]:
    """Generate clientid and nickname."""
    uuid = await instance_id.async_get(hass)
    return uuid, NICKNAME.format(instance_id=uuid[:6])

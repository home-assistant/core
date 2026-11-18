"""The Code Mode integration."""

from contextlib import AsyncExitStack

from pydantic_monty import AsyncMonty

from homeassistant.components.conversation import DATA_CODE_MODE
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.typing import ConfigType

from .api import async_create_api_instance
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

MAX_WORKERS = 4
CHECKOUT_TIMEOUT = 10


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start the sandbox worker pool."""
    stack = AsyncExitStack()
    pool = await stack.enter_async_context(
        AsyncMonty(max_processes=MAX_WORKERS, checkout_timeout=CHECKOUT_TIMEOUT)
    )

    @callback
    def async_wrap_api_instance(api_instance: llm.APIInstance) -> llm.APIInstance:
        return async_create_api_instance(pool, api_instance)

    hass.data[DATA_CODE_MODE] = async_wrap_api_instance

    async def _async_stop_pool(_: Event) -> None:
        await stack.aclose()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_stop_pool)
    return True

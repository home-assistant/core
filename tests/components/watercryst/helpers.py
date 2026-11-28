"""Various helper moethods."""

# from collections.abc import Callable
# from copy import copy
# from unittest.mock import AsyncMock

from pydantic import BaseModel
from pytest_homeassistant.common import async_load_json_object_fixture

from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.core import HomeAssistant


async def async_load_model_fixture[T: BaseModel](
    hass: HomeAssistant, filename: str, model: type[T]
) -> T:
    """Load a pydantic typed JSON object from a fixture."""
    obj = await async_load_json_object_fixture(hass, filename, DOMAIN)
    return model.model_validate(obj)


# def mock_return_value[T](mock: AsyncMock, modify: Callable[[T], None]) -> None:
#     """Modify the return value of a mock."""
#     data = copy(mock.return_value)
#     modify(data)
#     mock.return_value = data

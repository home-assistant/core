"""Update coordinator for Ruuvi Gateway."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioruuvigateway.api import get_gateway_history_data
from aioruuvigateway.models import TagData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class RuuviGatewayUpdateCoordinator(DataUpdateCoordinator[list[TagData]]):
    """Polls the gateway for data and returns a list of TagData objects that have changed since the last poll."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta | None = None,
        host: str,
        token: str,
    ) -> None:
        """Initialize the coordinator using the given configuration (host, token)."""
        super().__init__(hass, logger, name=name, update_interval=update_interval)
        self.host = host
        self.token = token
        self.last_tag_datas: dict[str, TagData] = {}

    async def _async_update_data(self) -> list[TagData]:
        changed_tag_datas: list[TagData] = []
        async with get_async_client(self.hass) as client:
            data = await get_gateway_history_data(
                client,
                host=self.host,
                bearer_token=self.token,
            )
        for tag in data.tags:
            if (
                tag.mac not in self.last_tag_datas
                or self.last_tag_datas[tag.mac].data != tag.data
            ):
                changed_tag_datas.append(tag)
                self.last_tag_datas[tag.mac] = tag
        return changed_tag_datas

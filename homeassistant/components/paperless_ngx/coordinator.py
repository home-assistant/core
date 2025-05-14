"""Paperless-ngx Status coordinator."""

from dataclasses import dataclass
from datetime import timedelta

from pypaperless import Paperless
from pypaperless.models import Tag
from pypaperless.models.status import Status

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PaperlessConfigEntry
from .const import LOGGER


@dataclass(frozen=True, kw_only=True)
class PaperlessData:
    """Describes Paperless-ngx sensor entity."""

    status: Status | None = None
    document_count: int | None = None
    inbox_count: int | None = None


class PaperlessCoordinator(DataUpdateCoordinator[PaperlessData]):
    """Coordinator to manage Paperless-ngx status updates."""

    def __init__(
        self, hass: HomeAssistant, entry: PaperlessConfigEntry, api: Paperless
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Paperless-ngx Status",
            config_entry=entry,
            update_interval=timedelta(seconds=10),
            always_update=True,
        )
        self.api = api
        self._inbox_tags: list[Tag] | None = None

    async def _async_setup(self):
        self._inbox_tags = [tag async for tag in self.api.tags if tag.is_inbox_tag]

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return PaperlessData(
                status=await self.get_paperless_status(self.api),
                document_count=await self.get_document_count(self.api),
                inbox_count=await self.get_inbox_count(self.api),
            )
        except Exception:
            LOGGER.debug(
                "An error occurred while updating the Paperless-ngx sensor",
                exc_info=True,
            )
            raise

    async def get_paperless_status(self, api: Paperless) -> Status | None:
        """Get the status of Paperless-ngx."""
        try:
            return await api.status()
        except Exception as err:  # noqa: BLE001
            LOGGER.warning(
                "An error occurred while updating the Paperless-ngx status data",
                err,
            )
            return None

    async def get_document_count(self, api: Paperless) -> int | None:
        """Get the number of documents in the system."""
        documents = await api.documents.all()
        return len(documents)

    async def get_inbox_count(self, api: Paperless) -> int | None:
        """Get the number of documents in the inbox."""
        if not self._inbox_tags:
            return 0

        tag_ids = ",".join(
            [str(tag.id) for tag in self._inbox_tags if tag.id is not None]
        )
        async with api.documents.reduce(tags__id__in=tag_ids) as docs:
            inbox_docs = await docs.all()

        return len(inbox_docs)

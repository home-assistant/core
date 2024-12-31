"""The coordinator for the ElevenLabs integration."""

from datetime import UTC, datetime, timedelta
from logging import getLogger

from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core import ApiError
from elevenlabs.types import UsageCharactersResponseModel

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=120)
BREAKDOWN_KEY = "All"


class ElevenLabsDataUpdateCoordinator(
    DataUpdateCoordinator[UsageCharactersResponseModel]
):
    """Class to manage fetching ElevenLabs data."""

    def __init__(self, hass: HomeAssistant, client: AsyncElevenLabs) -> None:
        """Initialize the ElevenLabs data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client
        self.usage_data: list[int] = []
        self.times: list[int] = []
        self.last_unix_update = 1

    def merge_usage_data(
        self, usage_data: UsageCharactersResponseModel
    ) -> UsageCharactersResponseModel:
        """Merge new usage data to the coordinator. Returns the merged data."""
        if BREAKDOWN_KEY not in usage_data.usage:
            _LOGGER.warning(
                "No data found for breakdown key %s in ElevenLabs usage response!",
                BREAKDOWN_KEY,
            )
            return UsageCharactersResponseModel(
                time=self.times, usage={BREAKDOWN_KEY: self.usage_data}
            )
        for idx, time in enumerate(usage_data.time):
            if time not in self.times:
                self.times.append(time)
                self.usage_data.append(usage_data.usage[BREAKDOWN_KEY][idx])
            else:
                self.usage_data[self.times.index(time)] = usage_data.usage[
                    BREAKDOWN_KEY
                ][idx]
        return UsageCharactersResponseModel(
            time=self.times, usage={BREAKDOWN_KEY: self.usage_data}
        )

    async def _async_update_data(self) -> UsageCharactersResponseModel:
        """Fetch data from ElevenLabs."""
        now = datetime.now(UTC)
        # Convert to milliseconds
        current_time_unix = int(now.timestamp() * 1_000)
        _LOGGER.debug(
            "Updating ElevenLabs usage data, start: %s, end: %s",
            self.last_unix_update,
            current_time_unix,
        )
        try:
            response = await self.client.usage.get_characters_usage_metrics(
                start_unix=self.last_unix_update, end_unix=current_time_unix
            )
            merged_response = self.merge_usage_data(response)
            current_date_unix = int(
                datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp() * 1_000
            )
            self.last_unix_update = current_date_unix
        except ApiError as e:
            _LOGGER.exception(
                "API Error when fetching usage data in ElevenLabs integration!"
            )
            raise UpdateFailed(
                "Error fetching usage data for ElevenLabs integration"
            ) from e
        except Exception as e:
            _LOGGER.exception(
                "Unknown error when fetching usage data in ElevenLabs integration!"
            )
            raise UpdateFailed(
                "Unknown error fetching usage data for ElevenLabs integration"
            ) from e
        return merged_response

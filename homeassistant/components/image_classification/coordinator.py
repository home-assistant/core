"""Coordinator classifying camera frames."""

from typing import override

from homeassistant.components import ai_task
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_REGION
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_AI_TASK_ENTITY_ID, DOMAIN, LOGGER, UPDATE_INTERVAL
from .frame_source import region_to_fractions
from .taught_frames import TaughtFrames

type ImageClassificationConfigEntry = ConfigEntry[ImageClassificationCoordinator]


class ImageClassificationCoordinator(
    DataUpdateCoordinator[ai_task.ClassifyImageResult | None]
):
    """Classify the current camera frame with an AI Task entity."""

    config_entry: ImageClassificationConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ImageClassificationConfigEntry,
        taught_frames: TaughtFrames,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL,
        )
        self.taught_frames = taught_frames

    @override
    async def _async_update_data(self) -> ai_task.ClassifyImageResult | None:
        """Return the answer, None while not taught or unsure."""
        if not self.taught_frames.ready:
            # Nothing to compare with yet; spare the camera and the model.
            return None
        if self.hass.state is not CoreState.running:
            # The camera or the AI Task entity may not be set up yet;
            # refreshed once started.
            return None
        options = self.config_entry.options
        try:
            return await ai_task.async_classify_image(
                self.hass,
                task_name=self.config_entry.title,
                image={
                    "media_content_id": (
                        f"media-source://camera/{options[CONF_ENTITY_ID]}"
                    ),
                    # AI Task asks the camera for its content type.
                    "media_content_type": "image/jpeg",
                },
                labels=self.taught_frames.labels(),
                region=region_to_fractions(options[CONF_REGION]),
                entity_id=options[CONF_AI_TASK_ENTITY_ID],
            )
        except ai_task.ImageUnusableError:
            # A dark night can look the same as a camera showing nothing.
            return None
        except HomeAssistantError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="classification_failed",
                translation_placeholders={"error": str(err)},
            ) from err

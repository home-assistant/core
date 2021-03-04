"""Spokestack Wakeword Component."""
import logging
import os

import requests

from .const import DOMAIN, FILE_NAMES, SAVE_PATH
from .pipeline_builder import build_pipeline

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up Spokestack Wakeword service."""

    hass.data.setdefault(DOMAIN, {})

    pipeline = build_pipeline()

    @pipeline.event
    def on_activate(context):  # pylint: disable=unused-variable
        """Fire event if the wake word is detected."""
        hass.bus.async_fire("spokestack_wakeword_detected")

    def start_service(call):
        """Start the pipeline service."""
        pipeline.start()
        _LOGGER.info("pipeline started")

    def run_service(call):
        """Run the wake word service."""
        _LOGGER.info("pipeline running")
        pipeline.run()

    def stop_service(call):
        """Stop the wake word service."""
        pipeline.stop()
        _LOGGER.info("pipeline stopped")

    # Register wake word services with Home Assistant.
    hass.services.async_register(DOMAIN, "start", start_service)
    hass.services.async_register(DOMAIN, "run", run_service)
    hass.services.async_register(DOMAIN, "stop", stop_service)

    # Return boolean to indicate that initialization was successfully.
    return True


async def async_setup_entry(hass, entry):
    """Download wake word models."""
    url = entry.data["model_url"]
    try:
        hass.async_add_executor_job(_download_models, url)
        return True
    except requests.exceptions.RequestException:
        _LOGGER.error("Invalid model_url")
        return False


def _download_models(model_url):
    _LOGGER.info("Downloading Wake Word Models")
    os.makedirs(SAVE_PATH, exist_ok=True)
    for name in FILE_NAMES:
        req = requests.get(os.path.join(model_url, name))
        with open(os.path.join(SAVE_PATH, name), "wb") as file:
            file.write(req.content)

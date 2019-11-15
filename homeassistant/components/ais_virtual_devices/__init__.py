"""Set up the demo environment that mimics interaction with devices."""
import asyncio
import logging
import time
from homeassistant import bootstrap


DOMAIN = "ais_virtual_devices"
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the ais ais environment."""

    # Set up camera
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("camera", "ais_qrcode", {}, config)
    )

    # Set up ais dom devices (RF codes)
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            "sensor", "ais_dom_device", {}, config
        )
    )

    # Set up ais dom notify
    # hass.async_create_task(
    #     hass.helpers.discovery.async_load_platform(
    #         "notify", "ais_ai_service", {}, config
    #     )
    # )

    return True

    # TODO see demo platform
    # Set up ais_books_player
    # tasks = [
    #     bootstrap.async_setup_component(
    #         hass,
    #         "input_select",
    #         {
    #             "input_select": {
    #                 "book_autor": {
    #                     "name": "Autor",
    #                     "options": ["-"],
    #                     "icon": "mdi:human-greeting",
    #                 },
    #                 "book_name": {
    #                     "name": "Książka",
    #                     "options": ["-"],
    #                     "icon": "mdi:book-open-page-variant",
    #                 },
    #                 "book_chapter": {
    #                     "name": "Rozdział",
    #                     "options": ["-"],
    #                     "icon": "mdi:bookmark-music",
    #                 },
    #             }
    #         },
    #     )
    # ]
    #
    # results = await asyncio.gather(*tasks)
    #
    # if any(not result for result in results):
    #     return False
    #
    # return True

"""
Support for AIS Google Home

For more details about this component, please refer to the documentation at
https://www.ai-speaker.com
"""
import json
import logging

from homeassistant.components import ais_cloud
from homeassistant.components.ais_dom import ais_global

from .config_flow import configured_google_homes
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
aisCloudWS = None


async def async_setup(hass, config):
    """Register the service."""
    global aisCloudWS

    async def command(service):
        """ask service about info"""
        await _process_command(hass, service)

    hass.services.async_register(DOMAIN, "command", command)
    aisCloudWS = ais_cloud.AisCloudWS(hass)

    return True


async def _process_command(hass, call):
    try:
        question = call.data["text"]
        ret = await aisCloudWS.async_ask_json_gh(question, hass)
        if ret["success"]:
            # play audio returned by Google Assistant
            if "audio" in ret:
                _audio_info = {
                    # "IMAGE_URL": "",
                    "NAME": "Asystent",
                    "MEDIA_SOURCE": ais_global.G_AN_GOOGLE_ASSISTANT,
                    "media_content_id": "https://powiedz.co" + ret["audio"],
                }
                _audio_info = json.dumps(_audio_info)
                await hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                        "media_content_type": "ais_content_info",
                        "media_content_id": _audio_info,
                    },
                )

            # set text info in app
            if "response" in ret:
                m = ret["response"]
                if len(m) > 100:
                    hass.states.async_set(
                        "sensor.aisknowledgeanswer", m[0:100] + "...", {"text": m}
                    )
                else:
                    hass.states.async_set("sensor.aisknowledgeanswer", m, {"text": m})
        else:
            _LOGGER.error("Google answer: " + str(ret))
            try:
                _LOGGER.error("Google answer: " + str(ret.text))
            except:
                pass
            await hass.services.async_call(
                "ais_ai_service",
                "say_it",
                {
                    "text": "Błąd podczas pobierania odpowiedzi z Google, sprawdź w logach."
                },
            )
    except Exception as e:
        _LOGGER.error("e " + str(e))
        await hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Brak odpowiedzi z Google."}
        )
        return


async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # remove from cloud
    ws_ret = aisCloudWS.gh_ais_remove_integration()
    response = ws_ret.json()
    _LOGGER.info(response["message"])
    #
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True

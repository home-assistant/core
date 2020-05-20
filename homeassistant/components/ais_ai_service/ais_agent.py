from typing import Optional

from homeassistant.components.conversation import agent
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent


class AisAgent(agent.AbstractConversationAgent):
    """AIS dom conversation agent."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the agent."""
        self.hass = hass

    @property
    def attribution(self):
        """Return the attribution."""
        if self.hass.services.has_service("conversation", "process"):
            name = "Komendy > "
        name += "Asystent AIS"
        if self.hass.services.has_service("ais_google_home", "command"):
            name += " > Google Home"
        return {
            "name": name,
            "url": "https://www.ai-speaker.com/docs/ais_app_ai_integration",
        }

    async def async_get_onboarding(self):
        """Get onboard url if not onboarded."""
        # return { "text": "Would you like to opt-in to share your anonymized commands with Stanford to improve
        # Almond's responses?", "url": f"{host}/conversation", }
        return None

    async def async_set_onboarding(self, shown):
        """Set onboarding status."""
        # TODO
        return True

    async def async_process(
        self, text: str, context: Context, conversation_id: Optional[str] = None
    ) -> intent.IntentResponse:
        """Process a sentence."""
        from homeassistant.components import ais_ai_service as ais_ai

        intent_result = await ais_ai._async_process(self.hass, text)
        if intent_result is None:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech(
                "Przepraszam, jeszcze tego nie potrafię zrozumieć."
            )

        return intent_result

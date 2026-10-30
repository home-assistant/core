"""Agent foundation for conversation integration."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from homeassistant.core import Context
from homeassistant.helpers import intent, llm

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.tts import PcmFormat


@dataclass(frozen=True)
class AgentInfo:
    """Container for conversation agent info."""

    id: str
    name: str
    supports_streaming: bool
    supports_audio_input: bool = False
    supports_audio_output: bool = False


@dataclass(frozen=True, slots=True)
class ConversationAudioInput:
    """Spoken audio of the user."""

    pcm_format: PcmFormat
    """Format of the raw PCM audio."""

    stream: AsyncIterable[bytes]
    """Audio chunks until the end of the voice command."""


class ConversationAudioOutput(Protocol):
    """Destination for the spoken response of an agent."""

    def async_set_audio_stream(
        self, pcm_format: PcmFormat, audio_stream: AsyncGenerator[bytes]
    ) -> None:
        """Set the raw PCM audio of the spoken response."""


@dataclass(slots=True)
class ConversationInput:
    """User input to be processed."""

    text: str
    """User spoken text. Empty when the spoken audio is provided instead."""

    context: Context
    """Context of the request."""

    conversation_id: str | None
    """Unique identifier for the conversation."""

    device_id: str | None
    """Unique identifier for the device."""

    satellite_id: str | None
    """Unique identifier for the satellite."""

    language: str
    """Language of the request."""

    agent_id: str
    """Agent to use for processing."""

    extra_system_prompt: str | None = None
    """Extra prompt to provide extra info to LLMs how to understand the command."""

    audio: ConversationAudioInput | None = None
    """Spoken audio of the user, only for agents that support audio input.

    The agent adds the transcript of the audio to the chat log as user content,
    if it has one.
    """

    audio_output: ConversationAudioOutput | None = None
    """Where to send the spoken response, only for agents that support audio output."""

    def as_dict(self) -> dict[str, Any]:
        """Return input as a dict."""
        result: dict[str, Any] = {
            "text": self.text,
            "context": self.context.as_dict(),
            "conversation_id": self.conversation_id,
            "device_id": self.device_id,
            "satellite_id": self.satellite_id,
            "language": self.language,
            "agent_id": self.agent_id,
            "extra_system_prompt": self.extra_system_prompt,
        }
        if self.audio is not None:
            result["audio"] = {"pcm_format": asdict(self.audio.pcm_format)}
        return result

    def as_llm_context(self, conversing_domain: str) -> llm.LLMContext:
        """Return input as an LLM context."""
        return llm.LLMContext(
            platform=conversing_domain,
            context=self.context,
            language=self.language,
            assistant=DOMAIN,
            device_id=self.device_id,
            agent_id=self.agent_id,
        )


@dataclass(slots=True)
class ConversationResult:
    """Result of async_process."""

    response: intent.IntentResponse
    conversation_id: str | None = None
    continue_conversation: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return result as a dict."""
        return {
            "response": self.response.as_dict(),
            "conversation_id": self.conversation_id,
            "continue_conversation": self.continue_conversation,
        }


class AbstractConversationAgent(ABC):
    """Abstract conversation agent."""

    @property
    @abstractmethod
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""

    @abstractmethod
    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""

    async def async_reload(self, language: str | None = None) -> None:  # noqa: B027
        """Clear cached intents for a language."""

    async def async_prepare(self, language: str | None = None) -> None:  # noqa: B027
        """Load intents for a language."""

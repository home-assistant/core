"""Constants for the Amazon Bedrock Agent integration test."""
from typing import Final

CONST_PROMPT: Final = "Hello there."
CONST_PROMPT_CONTEXT: Final = "Provide a short answer to: "

CONST_RESPONSES: Final = {
    "anthropic.claude-v2:1": {
        "completion": "General Kenobi.",
        "stop_reason": "stop_sequence",
        "stop": "\n\nHuman:",
    },
    "amazon.titan-text-express-v1": {
        "inputTextTokenCount": 10,
        "results": [
            {
                "tokenCount": 10,
                "outputText": "\nHi! How can I assist you today?",
                "completionReason": "FINISH",
            }
        ],
    },
}
CONST_ANSWERS: Final = {
    "anthropic.claude-v2:1": "General Kenobi.",
    "amazon.titan-text-express-v1": "\nHi! How can I assist you today?",
}

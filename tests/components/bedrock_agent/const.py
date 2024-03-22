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
    "anthropic.claude-v2": {
        "completion": " Hello.",
        "stop_reason": "stop_sequence",
        "stop": "\n\nHuman:",
    },
    "anthropic.claude-instant-v1": {
        "completion": " Hi!",
        "stop_reason": "stop_sequence",
        "stop": "\n\nHuman:",
    },
    "ai21.j2-mid-v1": {
        "id": 1234,
        "completions": [
            {
                "data": {"text": "\nHello!"},
                "finishReason": {"reason": "endoftext"},
            }
        ],
    },
    "ai21.j2-ultra-v1": {
        "id": 1234,
        "prompt": {
            "text": "Provide me a short answer to: Hello there.",
            "tokens": [],
        },
        "completions": [
            {
                "data": {"text": "\nHi, there.", "tokens": []},
                "finishReason": {"reason": "endoftext"},
            }
        ],
    },
    "mistral.mistral-7b-instruct-v0:2": {
        "outputs": [
            {
                "text": " Hello! How can I help you today? If you have a specific question, feel free to ask. If not, have a great day!",
                "stop_reason": "stop",
            }
        ]
    },
    "mistral.mixtral-8x7b-instruct-v0:1": {
        "outputs": [
            {"text": "\n\nHello! How can I assist you today?", "stop_reason": "stop"}
        ]
    },
}

CONST_ANSWERS: Final = {
    "anthropic.claude-v2:1": "General Kenobi.",
    "amazon.titan-text-express-v1": "\nHi! How can I assist you today?",
    "anthropic.claude-v2": " Hello.",
    "anthropic.claude-instant-v1": " Hi!",
    "ai21.j2-mid-v1": "\nHello!",
    "ai21.j2-ultra-v1": "\nHi, there.",
    "mistral.mistral-7b-instruct-v0:2": " Hello! How can I help you today? If you have a specific question, feel free to ask. If not, have a great day!",
    "mistral.mixtral-8x7b-instruct-v0:1": "\n\nHello! How can I assist you today?",
}

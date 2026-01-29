"""Mock Bedrock API response fixtures for testing _async_handle_chat_log method."""


def create_simple_text_response(
    text: str = "The weather today is sunny with a high of 75°F.",
) -> dict:
    """Create a simple text response from Bedrock."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 20, "outputTokens": 15, "totalTokens": 35},
    }


def create_response_with_thinking(
    thinking: str = "Let me analyze this", text: str = "Here's the answer"
) -> dict:
    """Create response with thinking content (Claude DeepThink)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": f"<thinking>{thinking}</thinking>{text}"}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 45, "outputTokens": 60, "totalTokens": 105},
    }


def create_response_with_only_thinking(
    thinking: str = "I need to analyze this request more carefully before providing a response...",
) -> dict:
    """Create response with only thinking content (should trigger re-call)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": f"<thinking>{thinking}</thinking>"}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 30, "outputTokens": 20, "totalTokens": 50},
    }


def create_response_with_tool_use(
    tool_name: str = "turn_on_light", tool_input: dict | None = None
) -> dict:
    """Create response with tool use (no text)."""
    if tool_input is None:
        tool_input = {"entity_id": "light.living_room"}
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_abc123",
                            "name": tool_name,
                            "input": tool_input,
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 25, "outputTokens": 30, "totalTokens": 55},
    }


def create_response_with_text_and_tool_use() -> dict:
    """Create response with both text and tool use."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "I'll turn on the living room light for you."},
                    {
                        "toolUse": {
                            "toolUseId": "tool_def456",
                            "name": "turn_on_light",
                            "input": {"entity_id": "light.living_room"},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 30, "outputTokens": 40, "totalTokens": 70},
    }


def create_response_with_multiple_tool_uses() -> dict:
    """Create response with multiple tool calls."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "I'll check all the rooms for you."},
                    {
                        "toolUse": {
                            "toolUseId": "tool_room1",
                            "name": "get_temperature",
                            "input": {"room": "bedroom"},
                        }
                    },
                    {
                        "toolUse": {
                            "toolUseId": "tool_room2",
                            "name": "get_temperature",
                            "input": {"room": "living_room"},
                        }
                    },
                    {
                        "toolUse": {
                            "toolUseId": "tool_room3",
                            "name": "get_temperature",
                            "input": {"room": "kitchen"},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 35, "outputTokens": 75, "totalTokens": 110},
    }


def create_response_with_sanitized_tool_name() -> dict:
    """Create response with tool name that was sanitized (needs reverse mapping)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_sanitized",
                            "name": "my_complex_tool_name",  # Sanitized version
                            "input": {"action": "execute"},
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 28, "outputTokens": 35, "totalTokens": 63},
    }


def create_final_response_after_tool_results(
    text: str = "Based on the temperature readings, the bedroom is warmest at 78°F. I recommend turning on the AC.",
) -> dict:
    """Create final text response after tool execution."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 150, "outputTokens": 25, "totalTokens": 175},
    }


def create_response_with_structured_output(output_data: dict | None = None) -> dict:
    """Create response using structured output (tool call to structure)."""
    if output_data is None:
        output_data = {
            "devices": [
                {
                    "name": "Living Room Light",
                    "entity_id": "light.living_room",
                    "status": "on",
                },
                {
                    "name": "Bedroom Thermostat",
                    "entity_id": "climate.bedroom",
                    "status": "heat",
                    "temperature": 72,
                },
            ]
        }
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_structured",
                            "name": "device_list",
                            "input": output_data,
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 50, "outputTokens": 80, "totalTokens": 130},
    }


def create_response_with_unicode() -> dict:
    """Create response with Unicode characters."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "text": "I've turned on the café ☕ lights and set the temperature to 20°C 🌡️"
                    }
                ],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 30, "outputTokens": 20, "totalTokens": 50},
    }


def create_response_with_empty_content() -> dict:
    """Create edge case response with empty content array."""
    return {
        "output": {"message": {"role": "assistant", "content": []}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 0, "totalTokens": 10},
    }


def create_response_with_malformed_tool_use() -> dict:
    """Create response with malformed tool use (missing name)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_malformed",
                            # Missing 'name' field
                            "input": {"some": "data"},
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 20, "outputTokens": 15, "totalTokens": 35},
    }


def create_response_with_invalid_tool_name_type() -> dict:
    """Create response with invalid tool name type (not a string)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool_invalid",
                            "name": 123,  # Invalid: not a string
                            "input": {"action": "test"},
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 22, "outputTokens": 18, "totalTokens": 40},
    }


def create_response_sequence_for_iteration_test() -> list[dict]:
    """Create sequence of responses for testing multiple iterations."""
    return [
        # First iteration: Model requests tool to check brightness
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Let me check which room is brightest."},
                        {
                            "toolUse": {
                                "toolUseId": "tool_iter1",
                                "name": "get_light_brightness",
                                "input": {"area": "all"},
                            }
                        },
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 30, "outputTokens": 35, "totalTokens": 65},
        },
        # Second iteration: Model processes results and calls turn_off
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": "The living room is brightest. I'll turn off those lights."
                        },
                        {
                            "toolUse": {
                                "toolUseId": "tool_iter2",
                                "name": "turn_off_light",
                                "input": {"entity_id": "light.living_room"},
                            }
                        },
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 80, "outputTokens": 40, "totalTokens": 120},
        },
        # Third iteration: Final response after tool execution
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Done! I've turned off the living room lights."}
                    ],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 130, "outputTokens": 15, "totalTokens": 145},
        },
    ]


def create_nova_model_response(text: str = "I'll help you with that.") -> dict:
    """Create response typical of Nova models (with greedy decoding)."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": text},
                    {
                        "toolUse": {
                            "toolUseId": "tool_nova",
                            "name": "execute_automation",
                            "input": {"automation_id": "morning_routine"},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 40, "outputTokens": 30, "totalTokens": 70},
        "metrics": {"latencyMs": 250},
    }


def create_claude_model_response() -> dict:
    """Create response typical of Claude models."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "text": "I'll check the current weather conditions for you right away."
                    },
                    {
                        "toolUse": {
                            "toolUseId": "tool_claude",
                            "name": "get_weather",
                            "input": {},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 35, "outputTokens": 35, "totalTokens": 70},
        "metrics": {"latencyMs": 180},
    }


def create_response_with_long_text() -> dict:
    """Create response with very long text content."""
    long_text = " ".join(
        [
            f"This is sentence {i} of a detailed response explaining the automation system."
            for i in range(50)
        ]
    )
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": long_text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 100, "outputTokens": 500, "totalTokens": 600},
    }


def create_error_response_client_exception() -> Exception:
    """Create a client exception to simulate API errors."""
    return Exception("ClientError: ThrottlingException - Rate limit exceeded")


def create_error_response_service_exception() -> Exception:
    """Create a service exception."""
    return Exception(
        "ServiceException: Model is currently unavailable. Please try again later."
    )


def create_error_response_validation_exception() -> Exception:
    """Create a validation exception."""
    return Exception("ValidationException: Invalid parameter: messages cannot be empty")


# Response scenarios for documentation
BEDROCK_RESPONSE_SCENARIOS = {
    "simple_text": {
        "description": "Basic text response",
        "fixture": create_simple_text_response,
        "stop_reason": "end_turn",
        "has_tool_use": False,
    },
    "with_thinking": {
        "description": "Response with thinking content",
        "fixture": create_response_with_thinking,
        "stop_reason": "end_turn",
        "has_tool_use": False,
    },
    "only_thinking": {
        "description": "Response with only thinking (triggers re-call)",
        "fixture": create_response_with_only_thinking,
        "stop_reason": "end_turn",
        "has_tool_use": False,
        "triggers_iteration": True,
    },
    "tool_use": {
        "description": "Response with tool use",
        "fixture": create_response_with_tool_use,
        "stop_reason": "tool_use",
        "has_tool_use": True,
    },
    "text_and_tool": {
        "description": "Response with both text and tool use",
        "fixture": create_response_with_text_and_tool_use,
        "stop_reason": "tool_use",
        "has_tool_use": True,
    },
    "multiple_tools": {
        "description": "Response with multiple tool calls",
        "fixture": create_response_with_multiple_tool_uses,
        "stop_reason": "tool_use",
        "has_tool_use": True,
    },
    "sanitized_tool_name": {
        "description": "Tool name requiring reverse mapping",
        "fixture": create_response_with_sanitized_tool_name,
        "stop_reason": "tool_use",
        "has_tool_use": True,
    },
    "final_after_tools": {
        "description": "Final response after tool execution",
        "fixture": create_final_response_after_tool_results,
        "stop_reason": "end_turn",
        "has_tool_use": False,
    },
    "structured_output": {
        "description": "Structured output via tool use",
        "fixture": create_response_with_structured_output,
        "stop_reason": "tool_use",
        "has_tool_use": True,
    },
    "unicode": {
        "description": "Response with Unicode characters",
        "fixture": create_response_with_unicode,
        "stop_reason": "end_turn",
        "has_tool_use": False,
    },
    "empty_content": {
        "description": "Edge case with empty content",
        "fixture": create_response_with_empty_content,
        "stop_reason": "end_turn",
        "has_tool_use": False,
    },
    "malformed_tool": {
        "description": "Malformed tool use (missing name)",
        "fixture": create_response_with_malformed_tool_use,
        "stop_reason": "tool_use",
        "has_tool_use": True,
        "should_raise": True,
    },
    "invalid_tool_name_type": {
        "description": "Invalid tool name type",
        "fixture": create_response_with_invalid_tool_name_type,
        "stop_reason": "tool_use",
        "has_tool_use": True,
        "should_raise": True,
    },
    "iteration_sequence": {
        "description": "Multi-iteration response sequence",
        "fixture": create_response_sequence_for_iteration_test,
        "is_sequence": True,
    },
    "nova_model": {
        "description": "Nova model specific response",
        "fixture": create_nova_model_response,
        "model_type": "nova",
    },
    "claude_model": {
        "description": "Claude model specific response",
        "fixture": create_claude_model_response,
        "model_type": "claude",
    },
    "long_text": {
        "description": "Response with very long text",
        "fixture": create_response_with_long_text,
        "stop_reason": "end_turn",
    },
    "client_exception": {
        "description": "Client exception (throttling)",
        "fixture": create_error_response_client_exception,
        "is_exception": True,
    },
    "service_exception": {
        "description": "Service exception (unavailable)",
        "fixture": create_error_response_service_exception,
        "is_exception": True,
    },
    "validation_exception": {
        "description": "Validation exception",
        "fixture": create_error_response_validation_exception,
        "is_exception": True,
    },
}

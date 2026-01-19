"""
Test Guide for _async_handle_chat_log Method
=============================================

This guide explains how to use the chat log and response fixtures to test
the _async_handle_chat_log method comprehensively.

Overview
--------
The _async_handle_chat_log method is the core of the AWS Bedrock conversation
entity. It processes chat logs, calls the Bedrock API, handles tool execution,
manages attachments, and processes responses including thinking content.

Test Coverage Areas
------------------

1. **Basic Message Processing**
   - Simple text messages
   - System prompts
   - Conversation history
   - Unicode and special characters

2. **Tool Handling**
   - Tool detection and formatting
   - Tool name sanitization and mapping
   - Single and multiple tool calls
   - Tool result processing
   - Tool error handling
   - Tool iteration loops

3. **Attachment Processing**
   - Image attachments
   - PDF attachments
   - Multiple attachments
   - Missing file errors
   - Unsupported MIME types

4. **Response Processing**
   - Text responses
   - Thinking content removal
   - Mixed content (text + tools)
   - Empty responses
   - Malformed responses

5. **Model-Specific Behavior**
   - Nova model configuration (temperature=0, topK=1)
   - Claude model thinking content
   - Model-specific schema cleaning

6. **Error Scenarios**
   - API exceptions
   - Service errors
   - Validation errors
   - Malformed tool responses

7. **Edge Cases**
   - Very long content
   - Empty messages
   - JSON in content
   - Code blocks
   - Only thinking content (triggers re-call)

Test Structure Pattern
---------------------

```python
async def test_handle_chat_log_scenario(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test specific scenario.\"\"\"
    # Setup
    mock_config_entry.add_to_hass(hass)

    # Create mock Bedrock client
    mock_client = MagicMock()
    mock_config_entry.runtime_data = mock_client

    # Create entity
    subentry = create_mock_subentry(model="anthropic.claude-3-sonnet-20240229-v1:0")
    entity = AWSBedrockBaseLLMEntity(mock_config_entry, subentry)

    # Create chat log with content
    chat_log = MagicMock(spec=conversation.ChatLog)
    chat_log.content = create_simple_user_message()
    chat_log.llm_api = None  # Or create mock with tools
    chat_log.unresponded_tool_results = []

    # Mock async_add_assistant_content
    async def mock_add_assistant(content):
        yield  # Empty generator
    chat_log.async_add_assistant_content = mock_add_assistant

    # Configure Bedrock response
    mock_client.converse.return_value = create_simple_text_response()

    # Execute
    result = await entity._async_handle_chat_log(
        chat_log,
        structure=None,
        structure_name=None,
    )

    # Verify
    assert mock_client.converse.called
    call_args = mock_client.converse.call_args[1]
    assert call_args["modelId"] == "anthropic.claude-3-sonnet-20240229-v1:0"
    assert len(call_args["messages"]) == 1
    assert call_args["inferenceConfig"]["temperature"] == 0.7
```

Example Test Cases
-----------------

### Test 1: Simple Text Message
Tests basic message processing without tools or attachments.

```python
async def test_handle_chat_log_simple_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test simple text message processing.\"\"\"
    # Use fixture: create_simple_user_message()
    # Use response: create_simple_text_response()
    # Verify: 1 API call, correct message format, text response
```

### Test 2: Tool Use and Results
Tests tool detection, execution, and result processing.

```python
async def test_handle_chat_log_with_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test tool use detection and execution.\"\"\"
    # Setup chat_log.llm_api with mock tools
    # Use fixture: create_message_with_tool_use()
    # First response: create_response_with_tool_use()
    # Mock tool execution to add results to chat log
    # Second call: create_final_response_after_tool_results()
    # Verify: 2 API calls, tool name mapping, result processing
```

### Test 3: Multiple Tool Iterations
Tests the iteration loop and tool chaining.

```python
async def test_handle_chat_log_multiple_iterations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test multiple tool iterations.\"\"\"
    # Use fixture: create_message_requiring_multiple_tool_iterations()
    # Use response sequence: create_response_sequence_for_iteration_test()
    # Mock multiple tool executions
    # Verify: 3 iterations, tool chaining, final response
```

### Test 4: Image Attachments
Tests attachment processing and media source integration.

```python
async def test_handle_chat_log_with_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    \"\"\"Test image attachment processing.\"\"\"
    # Create test image file
    # Use fixture: create_message_with_attachments()
    # Mock media_source.async_resolve_media
    # Verify: image in message content, correct format
```

### Test 5: Thinking Content
Tests thinking tag removal (Claude models).

```python
async def test_handle_chat_log_thinking_content(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test thinking content removal.\"\"\"
    # Use fixture: create_message_with_thinking_content()
    # Use response: create_response_with_thinking()
    # Verify: thinking tags removed, clean text in result
```

### Test 6: Only Thinking Content (Re-call)
Tests the case where model produces only thinking, triggering a re-call.

```python
async def test_handle_chat_log_only_thinking_triggers_recall(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test model producing only thinking content triggers re-call.\"\"\"
    # First response: create_response_with_only_thinking()
    # Second response: create_simple_text_response()
    # Verify: 2 API calls, no message added after first call
```

### Test 7: Nova Model Configuration
Tests Nova-specific settings (temperature=0, topK=1).

```python
async def test_handle_chat_log_nova_model_with_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test Nova model specific configuration.\"\"\"
    # Create subentry with Nova model ID
    # Add tools to chat_log.llm_api
    # Verify: temperature=0, additionalModelRequestFields has topK=1
```

### Test 8: Error Handling
Tests various error scenarios.

```python
async def test_handle_chat_log_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test API error handling.\"\"\"
    # Configure mock to raise exception
    # Use fixture: create_error_response_client_exception()
    # Verify: HomeAssistantError raised with message
```

### Test 9: Tool Name Mapping
Tests bidirectional tool name mapping.

```python
async def test_handle_chat_log_tool_name_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test tool name sanitization and reverse mapping.\"\"\"
    # Create tool with special characters in name
    # Verify: name sanitized in request, mapped back in response
```

### Test 10: Structured Output
Tests structured output via tool mechanism.

```python
async def test_handle_chat_log_structured_output(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    \"\"\"Test structured output generation.\"\"\"
    # Call with structure and structure_name parameters
    # Verify: structure added as tool, schema cleaned for Nova
```

Mock Helper Functions
--------------------

```python
def create_mock_subentry(
    model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> Mock:
    \"\"\"Create a mock ConfigSubentry.\"\"\"
    subentry = Mock(spec=ConfigSubentry)
    subentry.subentry_id = "test_subentry"
    subentry.title = "Test Chat"
    subentry.data = {
        CONF_CHAT_MODEL: model,
        CONF_TEMPERATURE: temperature,
        CONF_MAX_TOKENS: max_tokens,
    }
    return subentry


def create_mock_tool(
    name: str = "test_tool",
    description: str = "A test tool",
    parameters: dict | None = None,
) -> llm.Tool:
    \"\"\"Create a mock Tool.\"\"\"
    if parameters is None:
        parameters = {
            "type": "object",
            "properties": {"param1": {"type": "string"}},
            "required": ["param1"],
        }

    return llm.Tool(
        name=name,
        description=description,
        parameters=parameters,
    )


def create_mock_llm_api(tools: list[llm.Tool] | None = None) -> Mock:
    \"\"\"Create a mock LLM API with tools.\"\"\"
    mock_api = Mock(spec=llm.API)
    mock_api.tools = tools or []
    mock_api.custom_serializer = None
    return mock_api


async def create_chat_log_with_tools(
    hass: HomeAssistant,
    content: list[conversation.Content],
    tools: list[llm.Tool] | None = None,
) -> Mock:
    \"\"\"Create a mock ChatLog with tools.\"\"\"
    chat_log = Mock(spec=conversation.ChatLog)
    chat_log.content = content
    chat_log.llm_api = create_mock_llm_api(tools) if tools else None
    chat_log.unresponded_tool_results = []

    # Mock async_add_assistant_content
    added_content = []

    async def mock_add_assistant(content):
        added_content.append(content)
        yield  # Empty generator

    chat_log.async_add_assistant_content = mock_add_assistant
    chat_log._added_content = added_content  # Store for verification

    return chat_log
```

Verification Patterns
--------------------

```python
# Verify API call count
assert mock_client.converse.call_count == expected_count

# Verify message format
call_args = mock_client.converse.call_args[1]
assert call_args["modelId"] == expected_model
assert len(call_args["messages"]) == expected_message_count

# Verify tool configuration
if tools_expected:
    assert "toolConfig" in call_args
    assert len(call_args["toolConfig"]["tools"]) == expected_tool_count

# Verify inference config
inference_config = call_args["inferenceConfig"]
assert inference_config["temperature"] == expected_temp
assert inference_config["maxTokens"] == expected_tokens

# Verify system prompt
if system_expected:
    assert "system" in call_args
    assert call_args["system"][0]["text"] == expected_system

# Verify Nova-specific fields
if is_nova_with_tools:
    assert "additionalModelRequestFields" in call_args
    assert call_args["additionalModelRequestFields"]["inferenceConfig"]["topK"] == 1

# Verify assistant content added
assert len(chat_log._added_content) == expected_content_count
assert chat_log._added_content[0].content == expected_text
assert chat_log._added_content[0].tool_calls == expected_tool_calls

# Verify attachments processed
if attachments_expected:
    messages = call_args["messages"]
    last_message = messages[-1]
    assert last_message["role"] == "user"
    # Check for image or document in content
    assert any("image" in str(c) or "document" in str(c) for c in last_message["content"])
```

Testing Checklist
----------------

Basic Functionality:
- [ ] Simple text message
- [ ] Message with system prompt
- [ ] Conversation with history
- [ ] Unicode and special characters
- [ ] Empty/minimal messages
- [ ] Very long messages

Tool Handling:
- [ ] Single tool use
- [ ] Multiple tool uses
- [ ] Tool results processing
- [ ] Tool name sanitization
- [ ] Tool name reverse mapping
- [ ] Failed tool execution
- [ ] Tool iteration loop
- [ ] Max iteration limit

Attachments:
- [ ] Single image attachment
- [ ] Multiple images
- [ ] PDF attachment
- [ ] Mixed attachment types
- [ ] Missing file error
- [ ] Unsupported MIME type

Response Processing:
- [ ] Text only response
- [ ] Tool use response
- [ ] Mixed text and tool response
- [ ] Thinking content removal
- [ ] Only thinking (triggers re-call)
- [ ] Empty response

Model-Specific:
- [ ] Nova with tools (temp=0, topK=1)
- [ ] Nova schema cleaning
- [ ] Claude thinking content
- [ ] Max tokens adjustment for tools

Error Handling:
- [ ] API client error
- [ ] Service unavailable
- [ ] Validation error
- [ ] Malformed response
- [ ] Invalid tool name

Structured Output:
- [ ] Basic structured output
- [ ] Structured output with Nova
- [ ] Complex schema

Integration:
- [ ] Full conversation flow
- [ ] Multiple iterations
- [ ] Mixed content types
- [ ] Real-world scenarios

Performance:
- [ ] Large attachment handling
- [ ] Many tool iterations
- [ ] Long conversations
- [ ] Token limit scenarios

Notes
-----
- Always mock the Bedrock client (entry.runtime_data)
- Always mock media_source for attachment tests
- Use tmp_path fixture for file operations
- Mock async_add_executor_job for synchronous testing
- Verify both request parameters and response processing
- Test error paths as well as happy paths
- Check iteration limits are enforced (MAX_TOOL_ITERATIONS)
"""

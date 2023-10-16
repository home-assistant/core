import os
import openai
import json

functions = [
    {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location", "unit"],
        },
    }
]
messages = [{"role": "user", "content": "How are you?"}]
# messages = [{"role": "user", "content": "What's the weather like in Boston today?"}]
completion = openai.ChatCompletion.create(
    model="gpt-4",
    messages=messages,
    functions=functions,
    function_call="auto",  # auto is default, but we'll be explicit
)
message = completion["choices"][0]["message"]

if "function_call" in message.keys():
    to_print = dict(message["function_call"])
    name = to_print["name"]
    arguments = json.loads(to_print["arguments"])
    print(type(to_print))
    print(to_print)
    print(type(name))
    print(name)
    print(type(arguments))
    print(arguments)
else:
    to_print = message["content"]
    print(type(to_print))
    print(to_print)

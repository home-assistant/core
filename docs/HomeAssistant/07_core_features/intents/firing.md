---
title: "Firing intents"
---

If your code matches the user's speech or text to intents, you can let the intent be handled by Home Assistant. This can be done from inside your own integration, or via the generic Intent handle API.

When you fire an intent, you will get a response back or an error will be raised. It is up to your code to return the result to the user.

## HTTP API

When the intent integration is loaded, an HTTP API endpoint is available at `/api/intent/handle`. You can POST JSON data to it containing an intent name and it's data:

```json
{
  "name": "HassTurnOn",
  "data": {
    "name": "Kitchen Light"
  }
}
```

## Home Assistant integration

Example code to handle an intent in Home Assistant.

```python
from homeassistant.helpers import intent

intent_type = "TurnLightOn"
slots = {"entity": {"value": "Kitchen"}}

try:
    intent_response = await intent.async_handle(
        hass, "example_component", intent_type, slots
    )

except intent.UnknownIntent as err:
    _LOGGER.warning("Received unknown intent %s", intent_type)

except intent.InvalidSlotInfo as err:
    _LOGGER.error("Received invalid slot data: %s", err)

except intent.IntentError:
    _LOGGER.exception("Error handling request for %s", intent_type)
```

The intent response is an instance of `homeassistant.helpers.intent.IntentResponse`.

| Name | Type | Description |
| ---- | ---- | ----------- |
| `intent` | Intent | Instance of intent that triggered response. |
| `speech` | Dictionary | Speech responses. Each key is a type. Allowed types are `plain` and `ssml`. |
| `reprompt` | Dictionary | Reprompt responses. Each key is a type. Allowed types are `plain` and `ssml`.<br />This is used to keep the session open when a response is required from the user. In these cases, `speech` usually is a question. |
| `card` | Dictionary | Card responses. Each key is a type. |

Speech dictionary values:

| Name | Type | Description |
| ---- | ---- | ----------- |
| `speech` | String | The text to say
| `extra_data` | Any | Extra information related to this speech.

Reprompt dictionary values:

| Name | Type | Description |
| ---- | ---- | ----------- |
| `reprompt` | String | The text to say when user takes too long to respond
| `extra_data` | Any | Extra information related to this speech.

Card dictionary values:

| Name | Type | Description |
| ---- | ---- | ----------- |
| `title` | String | The title of the card
| `content` | Any | The content of the card

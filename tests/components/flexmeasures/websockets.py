"""Tests for S2 protocol websockets integration."""
from datetime import datetime
from functools import partial
import json
import logging
import sys
import uuid

import rel
import websocket


def send(message: dict):
    """Send message over Home Assistant WebSocket API."""
    ws.send(json.dumps(message))


def send_s2_to_ha(message: dict):
    """Send S2 message over Home Assistant WebSocket API, as a message in the command phase."""
    # HA requires the "id" field, whose values must be coercible to an integer, and requires consecutive IDs to increase
    message["id"] = int(datetime.utcnow().timestamp() * 10**6)
    # HA requires the "type" field
    message["type"] = "S2"
    # message["type"] = "S2" + "." + message["message_type"]
    send(message)


def on_message(access_token, ws, message):
    """Test for receiving S2 messages."""
    message = json.loads(message)
    message_type = message.get("type")
    if message_type == "auth_required":
        logging.info("Authenticating...")
        send(
            {
                "type": "auth",
                "access_token": access_token,
            }
        )
    elif message_type == "auth_ok":
        logging.info("Authentication successful")
        send_s2_to_ha(
            {
                "message_id": str(
                    uuid.uuid4()
                ),  # IDs have to be locally unique strings (S2 JSON schema)
                "message_type": "FRBC.SystemDescription",
            }
        )
        # print("Subscribing to event...")
        # send(
        #     {
        #         "id": 1,
        #         "type": "subscribe_events",
        #         "event_type": "state_changed",
        #     }
        # )
        # print("Calling service...")
        # send(
        #     {
        #         "id": 24,
        #         "type": "call_service",
        #         "domain": "flexmeasures",
        #         "service": "s2",
        #         "service_data": {
        #             "name": '{"system_description": {}}',
        #         }
        #     }
        # )
    elif message_type == "event":
        logging.info(message)
    else:
        logging.info(message)
        # ws.send(input())


def on_error(ws, error):
    """Test for error."""
    logging.info(error)


def on_close(ws, close_status_code, close_msg):
    """Test for closing connection."""
    logging.info("### closed ###")


def on_open(ws):
    """Test for opening connection."""
    logging.info("Opened connection")


# todo: transform into unit tests
# async def test_form_invalid_auth(hass: HomeAssistant) -> None:
if __name__ == "__main__":
    """Call this script with 1 argument: your long-lived access token.

    Long-lived access tokens can be created using the "Long-Lived Access Tokens" section at the bottom of a user's Home Assistant profile page.
    You can also generate a long-lived access token using the websocket command `auth/long_lived_access_token`, which will create a long-lived access token for current user.
    """
    access_token = sys.argv[1]

    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        "ws://localhost:8123/api/websocket",
        on_open=on_open,
        on_message=partial(on_message, access_token),
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(
        dispatcher=rel, reconnect=5
    )  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    # rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()

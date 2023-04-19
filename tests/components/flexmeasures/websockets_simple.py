import rel
import websocket


def on_message(ws, message):
    print(message)
    ws.send(message)


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    print("Opened connection")


# todo: transform into unit tests
# async def test_form_invalid_auth(hass: HomeAssistant) -> None:
if __name__ == "__main__":
    """Call this script with 1 argument: your long-lived access token.

    Long-lived access tokens can be created using the "Long-Lived Access Tokens" section at the bottom of a user's Home Assistant profile page.
    You can also generate a long-lived access token using the websocket command `auth/long_lived_access_token`, which will create a long-lived access token for current user.
    """

    # websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        "ws://localhost:8123/api/websocket_custom",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(
        dispatcher=rel, reconnect=5
    )  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    # rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()

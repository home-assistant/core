"""Example tool for interacting with voice_assistant API."""
import argparse
import asyncio
import audioop
import logging
import wave

import aiohttp

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Create websocket session then POST audio data to HTTP API."""
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", help="Path to WAV file")
    parser.add_argument("--token", required=True, help="HA auth token")
    parser.add_argument("--pipeline", default="default", help="Pipeline name")
    parser.add_argument(
        "--server", default="localhost:8123", help="host:port of HA server"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    with wave.open(args.wav, "rb") as wav_file:
        rate = wav_file.getframerate()
        width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        audio_bytes = wav_file.readframes(wav_file.getnframes())

        # Convert to 16Khz, 16-bit, mono
        if channels != 1:
            audio_bytes = audioop.tomono(audio_bytes, width, 1.0, 1.0)

        if width != 2:
            audio_bytes = audioop.lin2lin(audio_bytes, width, 2)

        if rate != 16000:
            audio_bytes, _state = audioop.ratecv(audio_bytes, 2, 1, rate, 16000, None)

    url = f"ws://{args.server}/api/websocket"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as websocket:
            # Authenticate
            msg = await websocket.receive_json()
            assert msg["type"] == "auth_required", msg

            await websocket.send_json(
                {
                    "type": "auth",
                    "access_token": args.token,
                }
            )

            msg = await websocket.receive_json()
            assert msg["type"] == "auth_ok", msg

            # Run pipeline
            await websocket.send_json(
                {
                    "type": "voice_assistant/run",
                    "id": 1,
                    "name": args.pipeline,
                }
            )

            msg = await websocket.receive_json()
            session_id = msg["session_id"]
            _LOGGER.info("Got session id: %s", session_id)

            # POST raw audio data to HTTP API with session id
            url = f"http://{args.server}/api/voice_assistant/{args.pipeline}"
            headers = {
                "Authorization": f"Bearer {args.token}",
                "X-Speech-Content": "language=en-US; format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1",
            }

            async with session.post(
                f"{url}?session_id={session_id}", data=audio_bytes, headers=headers
            ) as response:
                http_task = asyncio.create_task(response.json())
                ws_task = asyncio.create_task(websocket.receive_json())
                pending = {ws_task, http_task}

                while True:
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )
                    if ws_task in done:
                        msg = ws_task.result()
                        _LOGGER.info(msg)
                        if msg["type"] == "result":
                            break

                        ws_task = asyncio.create_task(websocket.receive_json())
                        pending.add(ws_task)


if __name__ == "__main__":
    asyncio.run(main())

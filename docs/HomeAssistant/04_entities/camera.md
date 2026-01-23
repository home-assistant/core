---
title: Camera entity
sidebar_label: Camera
---

A camera entity can display images, and optionally a video stream. Derive a platform entity from [`homeassistant.components.camera.Camera`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/camera/__init__.py).

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name                     | Type                                | Default | Description                                                                                         |
| ------------------------ | ------------------------------------| ------- | --------------------------------------------------------------------------------------------------- |
| brand                    | <code>str &#124; None</code>        | `None`  | The brand (manufacturer) of the camera.                                                             |
| frame_interval           | `float`                             | 0.5     | The interval between frames of the stream.                                                          |
| is_on                    | `bool`                              | `True`  | Indication of whether the camera is on.                                                             |
| is_recording             | `bool`                              | `False` | Indication of whether the camera is recording. Used to determine `state`.                           |
| is_streaming             | `bool`                              | `False` | Indication of whether the camera is streaming. Used to determine `state`.                           |
| model                    | <code>str &#124; None</code>        | `None`  | The model of the camera.                                                                            |
| motion_detection_enabled | `bool`                              | `False` | Indication of whether the camera has motion detection enabled.                                      |
| use_stream_for_stills    | `bool`                              | `False` | Determines whether or not to use the `Stream` integration to generate still images                  |

### States

The state is defined by setting the properties above. The resulting state uses the `CameraState` enum to return one of the below members.

| Value       | Description                             |
|-------------|-----------------------------------------|
| `RECORDING` | The camera is currently recording.      |
| `STREAMING` | The camera is currently streaming.      |
| `IDLE`      | The camera is currently idle.           |


## Supported features

Supported features are defined by using values in the `CameraEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value    | Description                                  |
| -------- | -------------------------------------------- |
| `ON_OFF` | The device supports `turn_on` and `turn_off` |
| `STREAM` | The device supports streaming                |

## Methods

### Camera image

When the width and height are passed, scaling should be done on a best-effort basis. The UI will fall back to scaling at the display layer if scaling cannot be done by the camera.

- Return the smallest image that meets the minimum width and minimum height.

- When scaling the image, aspect ratio must be preserved. If the aspect ratio is not the same as the requested height or width, it is expected that the width and/or height of the returned image will be larger than requested.

- Pass on the width and height if the underlying camera is capable of scaling the image.

- If the integration cannot scale the image and returns a jpeg image, it will automatically be scaled by the camera integration when requested.

```python
class MyCamera(Camera):
    # Implement one of these methods.

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        raise NotImplementedError()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""

```

### Stream source

The stream source should return a url that is usable by ffmpeg (e.g. an RTSP url). Requires `CameraEntityFeature.STREAM`.

A camera entity with a stream source by default uses `StreamType.HLS` to tell the frontend to use an HLS feed with the `stream` component. This stream source will also be used with `stream` for recording.

```python
class MyCamera(Camera):

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""

```

A common way for a camera entity to render a camera still image is to pass the stream source to `async_get_image` in the `ffmpeg` component.

### WebRTC streams

WebRTC enabled cameras can be used by facilitating a direct connection with the home assistant frontend. This usage requires `CameraEntityFeature.STREAM` and the integration must implement the two following methods to support native WebRTC:
- `async_handle_async_webrtc_offer`: To initialize a WebRTC stream. Any messages/errors coming in async should be forwared to the frontend with the `send_message` callback.
- `async_on_webrtc_candidate`: The frontend will call it with any candidate coming in after the offer is sent.
The following method can optionally be implemented:
- `close_webrtc_session` (Optional): The frontend will call it when the stream is closed. Can be used to clean up things.

WebRTC streams do not use the `stream` component and do not support recording.
By implementing the WebRTC methods, the frontend assumes that the camera supports only WebRTC and therefore will not fallbac to HLS.

```python
class MyCamera(Camera):

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle the async WebRTC offer.

        Async means that it could take some time to process the offer and responses/message
        will be sent with the send_message callback.
        This method is used by cameras with CameraEntityFeature.STREAM
        An integration overriding this method must also implement async_on_webrtc_candidate.

        Integrations can override with a native WebRTC implementation.
        """

    async def async_on_webrtc_candidate(self, session_id: str, candidate: RTCIceCandidate) -> None:
        """Handle a WebRTC candidate."""

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session."""
```

### WebRTC Providers

An integration may provide a WebRTC stream from an existing camera's stream source using the libraries in `homeassistant.components.camera.webrtc`. An
integration may implement `CameraWebRTCProvider` and register it with `async_register_webrtc_provider`.

### Turn on

```python
class MyCamera(Camera):
    # Implement one of these methods.

    def turn_on(self) -> None:
        """Turn on camera."""

    async def async_turn_on(self) -> None:
        """Turn on camera."""
```

### Turn off

```python
class MyCamera(Camera):
    # Implement one of these methods.

    def turn_off(self) -> None:
        """Turn off camera."""

    async def async_turn_off(self) -> None:
        """Turn off camera."""
```

### Enable motion detection

```python
class MyCamera(Camera):
    # Implement one of these methods.

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
```

### Disable motion detection

```python
class MyCamera(Camera):
    # Implement one of these methods.

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
```

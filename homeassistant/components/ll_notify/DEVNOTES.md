# Dev Notes

## HomeAssistant PR/Feedback
* [docs wrong: to_write](https://developers.home-assistant.io/docs/frontend/extending/websocket-api) - this is incorrect. Probably an old api. (There IS a `._to_write` but that is now clearly intended to be internal). I've used `hass.bus.async_fire`

## Misc
* Making the screen recording gif:
    1. Screen capture: Sh-Cmd-5
    2. Imovie
    3. Transform
    ```
    ffmpeg -i ~/Desktop/ll_notify.mp4 -filter:v scale=600:-1 -r 15  -f gif -loop -1 screenshot.gif
    ```
* Notes - you need .gitattributes to make sure git realizes gifs are binary!

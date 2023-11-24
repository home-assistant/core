Installation:
1. Create venv:
`virtualenv .venv && source .venv/bin/activate`

2. Install in editable mode:
`pip install -e .`

3. Run:
hass

3.1 Possibly, it will complain about `ffmpeg` not being installed. If so, just install it e.g. `brew install ffmpeg`.

4. for zigbee home automation, usb needs to be accessible by user:
`sudo chown $USER:$USER /dev/ttyACM0`

Post-Installation:
1. Add OpenAI-conversation integration and set it as default conversation agent
2. Add Zigbee Home Automation integration
3. Add devices via Zigbee Home Automation integration

Running:
1. Activate the virtualenv:
source .venv/bin/activate`

2. Run with make:
make start-hass

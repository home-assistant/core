AIS dom
=================================================================================

An open source audio and home automation platform that puts local action and privacy first.

![screenshot](https://raw.github.com/sviete/AIS-home-assistant/master/docs/screenshots.png)


### Developing on Linux:

1. Install the core dependencies.
```
sudo apt install python3.9
sudo apt install python3.9-dev
sudo apt install python3.9-venv
sudo apt install python3.9-pip
sudo apt install git autoconf libssl-dev libxml2-dev libxslt1-dev libjpeg-dev libffi-dev libudev-dev zlib1g-dev pkg-config libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libavresample-dev libavfilter-dev ffmpeg
```

2. Download this repository:
```
git clone https://github.com/sviete/AIS-home-assistant.git
cd AIS-home-assistant
```

2. Install the requirements with a provided script

```
./script/setup
```

3. Activate your virtual environment
```
source venv/bin/activate
```

4. Run AIS
```
hass -c /data/data/pl.sviete.dom/files/home/AIS

```

5. Open app in browser http://localhost:8180

![screenshot](https://raw.github.com/sviete/AIS-home-assistant/beta/docs/dev.png)


### Debugging in PyCharm:

1. Install PyCharm IDE
https://www.jetbrains.com/pycharm/download/#section=linux

2. Add a configuration to project

![screenshot](https://raw.github.com/sviete/AIS-home-assistant/beta/docs/ide.png)

3. Add some break point and start debugging

![screenshot](https://raw.github.com/sviete/AIS-home-assistant/beta/docs/debug.png)

# Home Assistant [![Build Status](https://travis-ci.org/balloob/home-assistant.svg?branch=master)](https://travis-ci.org/balloob/home-assistant) [![Coverage Status](https://img.shields.io/coveralls/balloob/home-assistant.svg)](https://coveralls.io/r/balloob/home-assistant?branch=master) [![Join the chat at https://gitter.im/balloob/home-assistant](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/balloob/home-assistant?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Home Assistant is a home automation platform running on Python 3. The goal of Home Assistant is to be able to track and control all devices at home and offer a platform for automating control. [Open a demo.](https://home-assistant.io/demo/)

Check out [the website](https://home-assistant.io) for installation instructions, tutorials and documentation.

[![screenshot-states](https://raw.github.com/balloob/home-assistant/master/docs/screenshots.png)](https://home-assistant.io/demo/)

Examples of devices it can interface it:

 * Monitoring connected devices to a wireless router: [OpenWrt](https://openwrt.org/), [Tomato](http://www.polarcloud.com/tomato), [Netgear](http://netgear.com), [DD-WRT](http://www.dd-wrt.com/site/index), [TPLink](http://www.tp-link.us/)
 * [Philips Hue](http://meethue.com) lights, [WeMo](http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/) switches, and [Tellstick](http://www.telldus.se/products/tellstick) devices and sensors
 * [Google Chromecasts](http://www.google.com/intl/en/chrome/devices/chromecast), [Music Player Daemon](http://www.musicpd.org/) and [Kodi (XBMC)](http://kodi.tv/)
 * Support for [ISY994](https://www.universal-devices.com/residential/isy994i-series/) (Insteon and X10 devices), [Z-Wave](http://www.z-wave.com/), [Nest Thermostats](https://nest.com/), and [Modbus](http://www.modbus.org/)
 * Integrate data from the [Bitcoin](https://bitcoin.org) network, local meteorological data from [OpenWeatherMap](http://openweathermap.org/), [Transmission](http://www.transmissionbt.com/) or [SABnzbd](http://sabnzbd.org).
 * [See full list of supported devices](https://home-assistant.io/components/)

Built home automation on top of your devices:

 * Keep a precise history of every change to the state of your house
 * Turn on the lights when people get home after sun set
 * Turn on lights slowly during sun set to compensate for less light
 * Turn off all lights and devices when everybody leaves the house
 * Offers a [REST API](https://home-assistant.io/developers/api.html) for easy integration with other projects
 * Allow sending notifications using [Instapush](https://instapush.im), [Notify My Android (NMA)](http://www.notifymyandroid.com/), [PushBullet](https://www.pushbullet.com/), [PushOver](https://pushover.net/), and [Jabber (XMPP)](http://xmpp.org)

The system is built modular so support for other devices or actions can be implemented easily. See also the [section on architecture](https://home-assistant.io/developers/architecture.html) and the [section on creating your own components](https://home-assistant.io/developers/creating_components.html).

If you run into issues while using Home Assistant or during development of a component, reach out to the [Home Assistant help section](https://home-assistant.io/help/) how to reach us.

## Quick-start guide

Running Home Assistant requires [Python 3.4](https://www.python.org/). Run the following code to get up and running:

```
git clone --recursive https://github.com/balloob/home-assistant.git
python3 -m venv home-assistant
cd home-assistant
python3 -m homeassistant --open-ui
```

The last command will start the Home Assistant server and launch its web interface. By default Home Assistant looks for the configuration file `config/configuration.yaml`. A standard configuration file will be written if none exists.

If you are still exploring if you want to use Home Assistant in the first place, you can enable the demo mode by adding the `--demo-mode` argument to the last command.

Please see [the getting started guide](https://home-assistant.io/getting-started/) on how to further configure Home Assistant.

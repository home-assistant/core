# Home Assistant [![Build Status](https://travis-ci.org/balloob/home-assistant.svg?branch=master)](https://travis-ci.org/balloob/home-assistant) [![Coverage Status](https://img.shields.io/coveralls/balloob/home-assistant.svg)](https://coveralls.io/r/balloob/home-assistant?branch=master) [![Join the chat at https://gitter.im/balloob/home-assistant](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/balloob/home-assistant?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[demo]: https://home-assistant.io/demo/

Home Assistant is a home automation platform running on Python 3. The goal of Home Assistant is to be able to track and control all devices at home and offer a platform for automating control.

To get started:
```bash
python3 -m pip install homeassistant
hass --open-ui
```

Check out [the website](https://home-assistant.io) for [a demo][demo], installation instructions, tutorials and documentation.

[![screenshot-states](https://raw.github.com/balloob/home-assistant/master/docs/screenshots.png)][demo]

Examples of devices it can interface it:

 * Monitoring connected devices to a wireless router: [OpenWrt](https://openwrt.org/), [Tomato](http://www.polarcloud.com/tomato), [Netgear](http://netgear.com), [DD-WRT](http://www.dd-wrt.com/site/index), [TPLink](http://www.tp-link.us/), [ASUSWRT](http://event.asus.com/2013/nw/ASUSWRT/) and any SNMP capable Linksys WAP/WRT
 * 
 * [Philips Hue](http://meethue.com) lights, [WeMo](http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/) switches, [Edimax](http://www.edimax.com/) switches, [Efergy](https://efergy.com) energy monitoring, RFXtrx sensors, and [Tellstick](http://www.telldus.se/products/tellstick) devices and sensors
 * [Google Chromecasts](http://www.google.com/intl/en/chrome/devices/chromecast), [Music Player Daemon](http://www.musicpd.org/), [Logitech Squeezebox](https://en.wikipedia.org/wiki/Squeezebox_%28network_music_player%29), [Plex](https://plex.tv/), [Kodi (XBMC)](http://kodi.tv/), and iTunes (by way of [itunes-api](https://github.com/maddox/itunes-api))
 * Support for [ISY994](https://www.universal-devices.com/residential/isy994i-series/) (Insteon and X10 devices), [Z-Wave](http://www.z-wave.com/), [Nest Thermostats](https://nest.com/), [RFXtrx](http://www.rfxcom.com/), [Arduino](https://www.arduino.cc/), [Raspberry Pi](https://www.raspberrypi.org/), and [Modbus](http://www.modbus.org/)
 * Interaction with [IFTTT](https://ifttt.com/)
 * Integrate data from the [Bitcoin](https://bitcoin.org) network, meteorological data from [OpenWeatherMap](http://openweathermap.org/) and [Forecast.io](https://forecast.io/), [Transmission](http://www.transmissionbt.com/), or [SABnzbd](http://sabnzbd.org).
 * [See full list of supported devices](https://home-assistant.io/components/)

Built home automation on top of your devices:

 * Keep a precise history of every change to the state of your house
 * Turn on the lights when people get home after sun set
 * Turn on lights slowly during sun set to compensate for less light
 * Turn off all lights and devices when everybody leaves the house
 * Offers a [REST API](https://home-assistant.io/developers/api.html) and can interface with MQTT for easy integration with other projects like [OwnTracks](http://owntracks.org/)
 * Allow sending notifications using [Instapush](https://instapush.im), [Notify My Android (NMA)](http://www.notifymyandroid.com/), [PushBullet](https://www.pushbullet.com/), [PushOver](https://pushover.net/), [Slack](https://slack.com/), [Telegram](https://telegram.org/), and [Jabber (XMPP)](http://xmpp.org)

The system is built modular so support for other devices or actions can be implemented easily. See also the [section on architecture](https://home-assistant.io/developers/architecture.html) and the [section on creating your own components](https://home-assistant.io/developers/creating_components.html).

If you run into issues while using Home Assistant or during development of a component, check the [Home Assistant help section](https://home-assistant.io/help/) how to reach us.

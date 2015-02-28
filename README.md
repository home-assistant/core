# Home Assistant [![Build Status](https://travis-ci.org/balloob/home-assistant.svg?branch=master)](https://travis-ci.org/balloob/home-assistant) [![Coverage Status](https://img.shields.io/coveralls/balloob/home-assistant.svg)](https://coveralls.io/r/balloob/home-assistant?branch=master)

This is the source code for Home Assistant. For installation instructions, tutorials and the docs, please see [the website](https://home-assistant.io). For a functioning demo frontend of Home Assistant, [click here](https://home-assistant.io/demo/).

Home Assistant is a home automation platform running on Python 3. The goal of Home Assistant is to be able to track and control all devices at home and offer a platform for automating control.

It offers the following functionality through built-in components:

 * Track if devices are home by monitoring connected devices to a wireless router (supporting [OpenWrt](https://openwrt.org/), [Tomato](http://www.polarcloud.com/tomato), [Netgear](http://netgear.com))
 * Track and control [Philips Hue](http://meethue.com) lights
 * Track and control [WeMo switches](http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/)
 * Track and control [Google Chromecasts](http://www.google.com/intl/en/chrome/devices/chromecast)
 * Track running services by monitoring `ps` output
 * Track and control [Tellstick devices and sensors](http://www.telldus.se/products/tellstick)
 * Turn on the lights when people get home after sun set
 * Turn on lights slowly during sun set to compensate for light loss
 * Turn off all lights and devices when everybody leaves the house
 * Offers web interface to monitor and control Home Assistant
 * Offers a [REST API](https://home-assistant.io/developers/api.html) for easy integration with other projects
 * [Ability to have multiple instances of Home Assistant work together](https://home-assistant.io/developers/architecture.html)

Home Assistant also includes functionality for controlling HTPCs:

 * Simulate key presses for Play/Pause, Next track, Prev track, Volume up, Volume Down
 * Download files
 * Open URLs in the default browser

[![screenshot-states](https://raw.github.com/balloob/home-assistant/master/docs/screenshots.png)](https://home-assistant.io/demo/)

The system is built modular so support for other devices or actions can be implemented easily. See also the [section on architecture](https://home-assistant.io/developers/architecture.html) and the [section on creating your own components](https://home-assistant.io/developers/creating_components.html).

If you run into issues while using Home Assistant or during development of a component, reach out to the [Home Assistant developer community](https://groups.google.com/forum/#!forum/home-assistant-dev).

## Installation instructions / Quick-start guide

Running Home Assistant requires that python 3.4 and the package requests are installed. Run the following code to install and start Home Assistant:

```python
git clone --recursive https://github.com/balloob/home-assistant.git
cd home-assistant
pip3 install -r requirements.txt
python3 -m homeassistant --open-ui
```

The last command will start the Home Assistant server and launch its webinterface. By default Home Assistant looks for the configuration file `config/home-assistant.conf`. A standard configuration file will be written if none exists.

If you are still exploring if you want to use Home Assistant in the first place, you can enable the demo mode by adding the `--demo-mode` argument to the last command.

Please see [the getting started guide](https://home-assistant.io/getting-started/) on how to further configure Home Asssitant.

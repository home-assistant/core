Home Assistant
==============

Home Assistant is a framework I wrote in Python to automate switching the lights on and off based on devices at home and the position of the sun.

It is currently able to do the following things:
 * Turn on the lights when one of the tracked devices gets home
 * Turn off the lights when everybody leaves home
 * Turn on the lights when the sun sets and one of the tracked devices is home (in progress)

It currently works with any wireless router with Tomato firmware in combination with the Philips Hue lightning system. The system is built modular so support for other wireless routers or other actions can be implemented easily.

Installation instructions
-------------------------

* install python modules [PyEphem](http://rhodesmill.org/pyephem/), [Requests](http://python-requests.org) and [PHue](https://github.com/studioimaginaire/phue)
* Clone the repository `git clone https://github.com/balloob/home-assistant.git`
* Copy home-assistant.conf.default to home-assistant.conf and adjust the config values to match your setup
  * For Tomato you will have to not only setup your host, username and password but also a http_id. This one can be found by inspecting your request to the tomato server.
* Setup PHue by running [this example script](https://github.com/studioimaginaire/phue/blob/master/examples/random_colors.py) with `b.connect()` uncommented
* The first time the script will start it will create a file called `tomato_known_devices.csv` which will contain the detected devices. Adjust the track variable for the devices you want the script to act on and restart the script.

Done. Start it now by running `python start.py`

Home Assistent Architecture and how to customize
------------------------------------------------

Home Assistent has been built from the ground up with extensibility and modularity in mind. It should be easy to swap in a different device tracker if I would move away from using a Tomato based firmware for my router for example. That is why all of Home Assistant has been built up on top of an event bus.

Different modules are able to fire and listen for specific events. On top of this is a state machine that allows modules to track the state of different things. Each device that is being tracked will have a state. Either home, home for 5 minutes, not home or not home for 5 minutes. On top of that there is also a state that is a combined state of all tracked devices.

This allows us to implement simple business rules to easily customize or extend functionality: 

    In the event that the state of device 'Paulus Nexus 4' changes to the 'Home' state:
      If the sun has set and the lights are not on:
        Turn on the lights
    
    In the event that the combined state of all tracked devices changes to 'Not Home':
      If the lights are on:
        Turn off the lights
        
    In the event of the sun setting:
      If the lights are off and the combined state of all tracked device is either 'Home' or 'Home for 5+ minutes':
        Turn on the lights

These rules are currently implemented in the file [HueTrigger.py](https://github.com/balloob/home-assistant/blob/master/app/actor/HueTrigger.py).

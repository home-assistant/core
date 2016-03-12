# Contributing to Home Assistant

Everybody is invited and welcome to contribute to Home Assistant. There is a lot to do...if you are not a developer perhaps you would like to help with the documentation on [home-assistant.io](https://home-assistant.io/)? If you are a developer and have devices in your home which aren't working with Home Assistant yet, why not spent a couple of hours and help to integrate them? 

The process is straight-forward.

 - Fork the Home Assistant [git repository](https://github.com/balloob/home-assistant).
 - Write the code for your device, notification service, sensor, or IoT thing.
 - Ensure tests work.
 - Create a Pull Request against the [**dev**](https://github.com/balloob/home-assistant/tree/dev) branch of Home Assistant.

Still interested? Then you should read the next sections and get more details. 

## Adding support for a new device

For help on building your component, please see the [developer documentation](https://home-assistant.io/developers/) on [home-assistant.io](https://home-assistant.io/).

After you finish adding support for your device:

 - Check that all dependencies are included via the `REQUIREMENTS` variable in your platform/component and only imported inside functions that use them.
 - Add any new dependencies to `requirements_all.txt` if needed. Use `script/gen_requirements_all.py`.
 - Update the `.coveragerc` file to exclude your platform if there are no tests available or your new code uses a 3rd party library for communication with the device/service/sensor.
 - Provide some documentation for [home-assistant.io](https://home-assistant.io/). It's OK to just add a docstring with configuration details (sample entry for `configuration.yaml` file and alike) to the file header as a start. Visit the [website documentation](https://home-assistant.io/developers/website/) for further information on contributing to [home-assistant.io](https://github.com/balloob/home-assistant.io).
 - Make sure all your code passes ``pylint`` and ``flake8`` (PEP8 and some more) validation. To check your repository, run `tox` or `script/lint`.
 - Create a Pull Request against the [**dev**](https://github.com/balloob/home-assistant/tree/dev) branch of Home Assistant.
 - Check for comments and suggestions on your Pull Request and keep an eye on the [CI output](https://travis-ci.org/balloob/home-assistant/).

If you add a platform for an existing component, there is usually no need for updating the frontend. Only if you've added a new component that should show up in the frontend, there are more steps needed:

 - Update the file [`home-assistant-icons.html`](https://github.com/balloob/home-assistant/blob/master/homeassistant/components/frontend/www_static/polymer/resources/home-assistant-icons.html) with an icon for your domain ([pick one from this list](https://www.polymer-project.org/1.0/components/core-elements/demo.html#core-icon)).
 - Update the demo component with two states that it provides.
 - Add your component to `home-assistant.conf.example`.

Since you've updated `home-assistant-icons.html`, you've made changes to the frontend:

 - Run `build_frontend`. This will build a new version of the frontend. Make sure you add the changed files `frontend.py` and `frontend.html` to the commit.

### Setting states

It is the responsibility of the component to maintain the states of the devices in your domain. Each device should be a single state and, if possible, a group should be provided that tracks the combined state of the devices.

A state can have several attributes that will help the frontend in displaying your state:

 - `friendly_name`: this name will be used as the name of the device
 - `entity_picture`: this picture will be shown instead of the domain icon
 - `unit_of_measurement`: this will be appended to the state in the interface
 - `hidden`: This is a suggestion to the frontend on if the state should be hidden

These attributes are defined in [homeassistant.components](https://github.com/balloob/home-assistant/blob/master/homeassistant/components/__init__.py#L25).

### Proper Visibility Handling

Generally, when creating a new entity for Home Assistant you will want it to be a class that inherits the [homeassistant.helpers.entity.Entity](https://github.com/balloob/home-assistant/blob/master/homeassistant/helpers/entity.py) class. If this is done, visibility will be handled for you. 
You can set a suggestion for your entity's visibility by setting the hidden property by doing something similar to the following.

```python
self.hidden = True
```

This will SUGGEST that the active frontend hides the entity. This requires that the active frontend support hidden cards (the default frontend does) and that the value of hidden be included in your attributes dictionary (see above). The Entity abstract class will take care of this for you.

Remember: The suggestion set by your component's code will always be overwritten by user settings in the configuration.yaml file. This is why you may set hidden to be False, but the property may remain True (or vice-versa).

### Working on the frontend

The frontend is composed of [Polymer](https://www.polymer-project.org) web-components and compiled into the file `frontend.html`. During development you do not want to work with the compiled version but with the seperate files. To have Home Assistant serve the seperate files, set `development=1` for the *http-component* in your config.

When you are done with development and ready to commit your changes, run `build_frontend`, set `development=0` in your config and validate that everything still works.

## Testing your code

To test your code before submission, used the `tox` tool.

```bash
> pip install -U tox
> tox
```

This will run unit tests against python 3.4 and 3.5 (if both are available locally), as well as run a set of tests which validate `pep8` and `pylint` style of the code.

You can optionally run tests on only one tox target using the `-e` option to select an environment.

For instance `tox -e lint` will run the linters only, `tox -e py34` will run unit tests only on python 3.4.

### Notes on PyLint and PEP8 validation

In case a PyLint warning cannot be avoided, add a comment to disable the PyLint check for that line. This can be done using the format `# pylint: disable=YOUR-ERROR-NAME`. Example of an unavoidable PyLint warning is if you do not use the passed in datetime if you're listening for time change.

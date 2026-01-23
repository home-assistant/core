---
title: Config flow
---

Integrations can be set up via the user interface by adding support for a config flow to create a config entry. Integrations that want to support config entries will need to define a Config Flow Handler. This handler will manage the creation of entries from user input, discovery or other sources (like Home Assistant OS).

Config Flow Handlers control the data that is stored in a config entry. This means that there is no need to validate that the config is correct when Home Assistant starts up. It will also prevent breaking changes because we will be able to migrate configuration entries to new formats if the version changes.

When instantiating the handler, Home Assistant will make sure to load all dependencies and install the requirements of the integration.

## Updating the manifest

You need to update your integrations manifest to inform Home Assistant that your integration has a config flow. This is done by adding `config_flow: true` to your manifest ([docs](creating_integration_manifest.md#config-flow)).

## Defining your config flow

Config entries use the [data flow entry framework](data_entry_flow_index.md) to define their config flows. The config flow needs to be defined in the file `config_flow.py` in your integration folder, extend `homeassistant.config_entries.ConfigFlow` and pass a `domain` key as part of inheriting `ConfigFlow`.

```python
from homeassistant import config_entries
from .const import DOMAIN


class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1
```

Once you have updated your manifest and created the `config_flow.py`, you will need to run `python3 -m script.hassfest` (one time only) for Home Assistant to activate the config entry for your integration.

## Config flow title

The title of a config flow can be influenced by integrations, and is determined in this priority order:

1. If `title_placeholders` is set to a non-empty dictionary in the config flow, it will be used to dynamically calculate the config flow's title. Reauth and reconfigure flows automatically set `title_placeholders` to `{"name": config_entry_title}`.
   1. If the integration provides a localized `flow_title`, that will be used, with any translation placeholders substituted from the `title_placeholders`.
   2. If the integration does not provide a `flow_title` but the `title_placeholders` includes a `name`, the `name` will be used as the flow's title.
2. Set the flow title to the integration's localized `title`, if it exists.
3. Set the flow title to the integration manifest's `name`, if it exists.
4. Set the flow title to the integration's domain.

Note that this priority order means that:
- A localized `flow_title` is ignored if the `title_placeholders` dictionary is missing or empty, even if the localized `flow_title` does not have any placeholders
- If `title_placeholders` is not empty, but there's no localized `flow_title` and the `title_placeholders` does not include a `name`, it is ignored.

## Defining steps

Your config flow will need to define steps of your configuration flow. Each step is identified by a unique step name (`step_id`). The step callback methods follow the pattern `async_step_<step_id>`. The docs for [Data Entry Flow](data_entry_flow_index.md) describe the different return values of a step. Here is an example of how to define the `user` step:

```python
import voluptuous as vol

class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info):
        if info is not None:
            pass  # TODO: process info

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required("password"): str})
        )
```

There are a few step names reserved for system use:

| Step name   | Description                                                                                                                                                   |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bluetooth`        | Invoked if your integration has been discovered via Bluetooth as specified [using `bluetooth` in the manifest](creating_integration_manifest.md#bluetooth).             |
| `discovery` | _DEPRECATED_ Invoked if your integration has been discovered and the matching step has not been defined.             |
| `dhcp`      | Invoked if your integration has been discovered via DHCP as specified [using `dhcp` in the manifest](creating_integration_manifest.md#dhcp).             |
| `hassio`    | Invoked if your integration has been discovered via a Supervisor add-on.
| `homekit`   | Invoked if your integration has been discovered via HomeKit as specified [using `homekit` in the manifest](creating_integration_manifest.md#homekit).         |
| `mqtt`      | Invoked if your integration has been discovered via MQTT as specified [using `mqtt` in the manifest](creating_integration_manifest.md#mqtt).             |
| `ssdp`      | Invoked if your integration has been discovered via SSDP/uPnP as specified [using `ssdp` in the manifest](creating_integration_manifest.md#ssdp).             |
| `usb`       | Invoked if your integration has been discovered via USB as specified [using `usb` in the manifest](creating_integration_manifest.md#usb).             |
| `user`      | Invoked when a user initiates a flow via the user interface or when discovered and the matching and discovery step are not defined.                                                                                                  |
| `reconfigure`      | Invoked when a user initiates a flow to reconfigure an existing config entry via the user interface.                                                                                                  |
| `zeroconf`  | Invoked if your integration has been discovered via Zeroconf/mDNS as specified [using `zeroconf` in the manifest](creating_integration_manifest.md#zeroconf). |
| `reauth`    | Invoked if your integration indicates it [requires reauthentication, e.g., due to expired credentials](#reauthentication). |
| `import`    | Reserved for migrating from YAML configuration to config entries. |

## Unique IDs

A config flow can attach a unique ID, which must be a string, to a config flow to avoid the same device being set up twice. The unique ID does not need to be globally unique, it only needs to be unique within an integration domain.

By setting a unique ID, users will have the option to ignore the discovery of your config entry. That way, they won't be bothered about it anymore.
If the integration uses Bluetooth, DHCP, HomeKit, Zeroconf/mDNS, USB, or SSDP/uPnP to be discovered, supplying a unique ID is required.

If a unique ID isn't available, alternatively, the `bluetooth`, `dhcp`, `zeroconf`, `hassio`, `homekit`, `ssdp`, `usb`, and `discovery` steps can be omitted, even if they are configured in
the integration manifest. In that case, the `user` step will be called when the item is discovered.

Alternatively, if an integration can't get a unique ID all the time (e.g., multiple devices, some have one, some don't), a helper is available
that still allows for discovery, as long as there aren't any instances of the integration configured yet.

Here's an example of how to handle discovery where a unique ID is not always available:

```python
if device_unique_id:
    await self.async_set_unique_id(device_unique_id)
else:
    await self._async_handle_discovery_without_unique_id()
```

### Managing Unique IDs in Config Flows

When a unique ID is set, the flow will immediately abort if another flow is in progress for this unique ID. You can also quickly abort if there is already an existing config entry for this ID. Config entries will get the unique ID of the flow that creates them.

Call inside a config flow step:

```python
# Assign a unique ID to the flow and abort the flow
# if another flow with the same unique ID is in progress
await self.async_set_unique_id(device_unique_id)

# Abort the flow if a config entry with the same unique ID exists
self._abort_if_unique_id_configured()
```

Should the config flow then abort, the text resource with the key `already_configured` from the `abort` part of your `strings.json` will be displayed to the user in the interface as an abort reason.

```json
{
  "config": {
    "abort": {
      "already_configured": "[%key:common::config_flow::abort::already_configured_device%]"
    }
  }
}
```

### Unique ID requirements

A unique ID is used to match a config entry to the underlying device or API. The unique ID must be stable, should not be able to be changed by the user and must be a string.

The Unique ID can be used to update the config entry data when device access details change. For example, for devices that communicate over the local network, if the IP address changes due to a new DHCP assignment, the integration can use the Unique ID to update the host using the following code snippet:

```
    await self.async_set_unique_id(serial_number)
    self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
```

#### Example acceptable sources for a unique ID

- Serial number of a device
- MAC address: formatted using `homeassistant.helpers.device_registry.format_mac`; Only obtain the MAC address from the device API or a discovery handler. Tools that rely on reading the arp cache or local network access such as `getmac` will not function in all supported network environments and are not acceptable.
- A string representing the latitude and longitude or other unique geo location
- Unique identifier that is physically printed on the device or burned into an EEPROM

#### Sometimes acceptable sources for a unique ID for local devices

- Hostname: If a subset of the hostname contains one of the acceptable sources, this portion can be used

#### Sometimes acceptable sources for a unique ID for cloud services

- Email Address: Must be normalized to lowercase
- Username: Must be normalized to lowercase if usernames are case-insensitive.
- Account ID: Must not have collisions

#### Unacceptable sources for a unique ID

- IP Address
- Device Name
- Hostname if it can be changed by the user
- URL

## Discovery steps

When an integration is discovered, their respective discovery step is invoked (ie `async_step_dhcp` or `async_step_zeroconf`) with the discovery information. The step will have to check the following things:

- Make sure there are no other instances of this config flow in progress of setting up the discovered device. This can happen if there are multiple ways of discovering that a device is on the network.
  - In most cases, it's enough to set the unique ID on the flow and check if there's already a config entry with the same unique ID as explained in the section about [managing unique IDs in config flows](#managing-unique-ids-in-config-flows)
  - In some cases, a unique ID can't be determined, or the unique ID is ambiguous because different discovery sources may have different ways to calculate it. In such cases:
    1. Implement the method `def is_matching(self, other_flow: Self) -> bool` on the flow.
    2. Call `hass.config_entries.flow.async_has_matching_flow(self)`.
    3. Your flow's `is_matching` method will then be called once for each other ongoing flow.
- Make sure that the device is not already set up.
- Invoking a discovery step should never result in a finished flow and a config entry. Always confirm with the user.

## Discoverable integrations that require no authentication

If your integration is discoverable without requiring any authentication, you'll be able to use the Discoverable Flow that is built-in. This flow offers the following features:

- Detect if devices/services can be discovered on the network before finishing the config flow.
- Support all manifest-based discovery protocols.
- Limit to only 1 config entry. It is up to the config entry to discover all available devices.

To get started, run `python3 -m script.scaffold config_flow_discovery` and follow the instructions. This will create all the boilerplate necessary to configure your integration using discovery.

## Configuration via OAuth2

Home Assistant has built-in support for integrations that offer account linking using [the OAuth2 authorization framework](https://www.rfc-editor.org/rfc/rfc6749). To be able to leverage this, you will need to structure your Python API library in a way that allows Home Assistant to be responsible for refreshing tokens. See our [API library guide](api_lib_index.md) on how to do this.

The built-in OAuth2 support works out of the box with locally configured client ID / secret using the [Application Credentials platform](/docs/core/platform/application_credentials) and with the Home Assistant Cloud Account Linking service. This service allows users to link their account with a centrally managed client ID/secret. If you want your integration to be part of this service, reach out to us at [partner@openhomefoundation.org](mailto:partner@openhomefoundation.org).

To get started, run `python3 -m script.scaffold config_flow_oauth2` and follow the instructions. This will create all the boilerplate necessary to configure your integration using OAuth2.

## Translations

[Translations for the config flow](/docs/internationalization/core#config--options--subentry-flows) handlers are defined under the `config` key in the integration translation file `strings.json`. Example of the Hue integration:

```json
{
  "title": "Philips Hue Bridge",
  "config": {
    "step": {
      "init": {
        "title": "Pick Hue bridge",
        "data": {
          "host": "Host"
        }
      },
      "link": {
        "title": "Link Hub",
        "description": "Press the button on the bridge to register Philips Hue with Home Assistant.\n\n![Location of button on bridge](/static/images/config_philips_hue.jpg)"
      }
    },
    "error": {
      "register_failed": "Failed to register, please try again",
      "linking": "Unknown linking error occurred."
    },
    "abort": {
      "discover_timeout": "Unable to discover Hue bridges",
      "no_bridges": "No Philips Hue bridges discovered",
      "all_configured": "All Philips Hue bridges are already configured",
      "unknown": "Unknown error occurred",
      "cannot_connect": "Unable to connect to the bridge",
      "already_configured": "Bridge is already configured"
    }
  }
}
```

When the translations are merged into Home Assistant, they will be automatically uploaded to [Lokalise](https://lokalise.co/) where the translation team will help to translate them in other languages. While developing locally, you will need to run `python3 -m script.translations develop` to see changes made to `strings.json` [More info on translating Home Assistant.](translations.md)

## Config entry migration

As mentioned above - each Config Entry has a version assigned to it. This is to be able to migrate Config Entry data to new formats when Config Entry schema changes.

Migration can be handled programmatically by implementing function `async_migrate_entry` in your integration's `__init__.py` file. The function should return `True` if migration is successful.

The version is made of a major and minor version. If minor versions differ but major versions are the same, integration setup will be allowed to continue even if the integration does not implement `async_migrate_entry`. This means a minor version bump is backwards compatible unlike a major version bump which causes the integration to fail setup if the user downgrades Home Assistant Core without restoring their configuration from backup.

```python
# Example migration function
async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating configuration from version %s.%s", config_entry.version, config_entry.minor_version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:

        new_data = {**config_entry.data}
        if config_entry.minor_version < 2:
            # TODO: modify Config Entry data with changes in version 1.2
            pass
        if config_entry.minor_version < 3:
            # TODO: modify Config Entry data with changes in version 1.3
            pass

        hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=3, version=1)

    _LOGGER.debug("Migration to configuration version %s.%s successful", config_entry.version, config_entry.minor_version)

    return True
```

## Reconfigure

A config entry can allow reconfiguration by adding a `reconfigure` step. This provides a way for integrations to allow users to change config entry data without the need to implement an `OptionsFlow` for changing setup data which is not meant to be optional.

This is not meant to handle authentication issues or reconfiguration of such. For that we have the [`reauth`](#reauthentication) step, which should be implemented to automatically start in such case there is an issue with authentication.

```python
import voluptuous as vol

class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Example integration."""

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # TODO: process user input
            self.async_set_unique_id(user_id)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required("input_parameter"): str}),
        )
```

On success, reconfiguration flows are expected to update the current entry and abort; they should not create a new entry.
This is usually done with the `return self.async_update_reload_and_abort` helper.
Automated tests should verify that the reconfigure flow updates the existing config entry and does not create additional entries.

Checking whether you are in a reconfigure flow can be done using `if self.source == SOURCE_RECONFIGURE`.
It is also possible to access the corresponding config entry using `self._get_reconfigure_entry()`.
Ensuring that the `unique_id` is unchanged should be done using `await self.async_set_unique_id` followed by `self._abort_if_unique_id_mismatch()`.


## Reauthentication

Gracefully handling authentication errors such as invalid, expired, or revoked tokens is needed to advance on the [Integration Quality Scale](core/integration-quality-scale). This example of how to add reauth to the OAuth flow created by `script.scaffold` following the pattern in [Building a Python library](api_lib_auth.md#oauth2).
If you are looking for how to trigger the reauthentication flow, see [handling expired credentials](integration_setup_failures.md#handling-expired-credentials).

This example catches an authentication exception in config entry setup in `__init__.py` and instructs the user to visit the integrations page in order to reconfigure the integration.

To allow the user to change config entry data which is not optional (`OptionsFlow`) and not directly related to authentication, for example a changed host name, integrations should implement the [`reconfigure`](#reconfigure) step.

```python

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.core import HomeAssistant
from . import api

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Setup up a config entry."""

    # TODO: Replace with actual API setup and exception
    auth = api.AsyncConfigEntryAuth(...)
    try:
        await auth.refresh_tokens()
    except TokenExpiredError as err:
        raise ConfigEntryAuthFailed(err) from err

    # TODO: Proceed with integration setup
```

The flow handler in `config_flow.py` also needs to have some additional steps to support reauth which include showing a confirmation, starting the reauth flow, updating the existing config entry, and reloading to invoke setup again.

```python

class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle OAuth2 authentication."""

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an oauth config entry or update existing entry for reauth."""
        self.async_set_unique_id(user_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
```

By default, the `async_update_reload_and_abort` helper method aborts the flow with `reauth_successful` after update and reload. By default, the entry will always be reloaded. If the config entry only should be reloaded in case the config entry was updated, specify `reload_even_if_entry_is_unchanged=False`.

Depending on the details of the integration, there may be additional considerations such as ensuring the same account is used across reauth, or handling multiple config entries.

The reauth confirmation dialog needs additional definitions in `strings.json` for the reauth confirmation and success dialogs:

```json
{
  "config": {
    "step": {
      "reauth_confirm": {
        "title": "[%key:common::config_flow::title::reauth%]",
        # TODO: Replace with the name of the integration
        "description": "The Example integration needs to re-authenticate your account"
      }
    },
    "abort": {
      "reauth_successful": "[%key:common::config_flow::abort::reauth_successful%]"
    },
}
```

See [Translations](#translations) local development instructions.

Authentication failures (such as a revoked oauth token) can be a little tricky to manually test. One suggestion is to make a copy of `config/.storage/core.config_entries` and manually change the values of `access_token`, `refresh_token`, and `expires_at` depending on the scenario you want to test. You can then walk advance through the reauth flow and confirm that the values get replaced with new valid tokens.

On success, reauth flows are expected to update the current entry and abort; they should not create a new entry.
This is usually done with the `return self.async_update_reload_and_abort` helper.
Automated tests should verify that the reauth flow updates the existing config entry and does not create additional entries.

Checking whether you are in a reauth flow can be done using `if self.source == SOURCE_REAUTH`.
It is also possible to access the corresponding config entry using `self._get_reauth_entry()`.
Ensuring that the `unique_id` is unchanged should be done using `await self.async_set_unique_id` followed by `self._abort_if_unique_id_mismatch()`.


## Subentry flows

An integration can implement subentry flows to allow users to add, and optionally reconfigure, subentries. An example of this is an integration providing weather forecasts, where the config entry stores authentication details and each location for which weather forecasts should be provided is stored as a subentry.

Subentry flows are similar to config flows, except that subentry flows don't support reauthentication or discovery; a subentry flow can only be initiated via the `user` or `reconfigure` steps.

```python
class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Example integration."""

    ...

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"location": LocationSubentryFlowHandler}

class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a location."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new location."""
        ...
```

### Subentry unique ID

Subentries can set a unique ID. The rules are similar to [unique IDs](#unique-ids) of config entries, except that subentry unique IDs only need to be unique within the config entry.

### Subentry translations

[Translations for subentry flow](/docs/internationalization/core#config--options--subentry-flows) handlers are defined under the `config_subentries` key in the integration translation file `strings.json`, for example:

```json
{
  "config_subentries": {
    "location": {
      "title": "Weather location",
      "step": {
        "user": {
          "title": "Add location",
          "description": "Configure the weather location"
        },
        "reconfigure": {
          "title": "Update location",
          "description": "..."
        }
      },
      "error": {
      },
      "abort": {
      }
    }
  }
}
```

### Subentry reconfigure

Subentries can be reconfigured, similar to how [config entries can be reconfigured](#reconfigure). To add support for reconfigure to a subentry flow, implement a `reconfigure` step.

```python
class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a location."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new location."""
        ...

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to modify an existing location."""
        # Retrieve the parent config entry for reference.
        config_entry = self._get_entry()
        # Retrieve the specific subentry targeted for update.
        config_subentry = self._get_reconfigure_subentry()
        ...

```

## Continuing in another flow

A config flow can start another config flow and tell the frontend that it should show the other flow once the first flow is finished. To do this the first flow needs to pass the `next_flow` parameter to the `async_create_entry` method. The argument should be a tuple of the form `(flow_type, flow_id)`.

```python
from homeassistant.config_entries import SOURCE_USER, ConfigFlow, FlowType


class ExampleFlow(ConfigFlow):
    """Example flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show create entry with next_flow parameter."""
        result = await self.hass.config_entries.flow.async_init(
            "another_integration_domain",
            context={"source": SOURCE_USER},
        )
        return self.async_create_entry(
            title="Example",
            data={},
            next_flow=(FlowType.CONFIG_FLOW, result["flow_id"]),
        )
```

## Use SchemaConfigFlowHandler for simple flows

For helpers and integrations with simple config flows, you can use the `SchemaConfigFlowHandler` instead.

Compared to using a full config flow, the `SchemaConfigFlowHandler` comes with certain limitations and needs to be considered:

- All user input is saved in the `options` dictionary of the resulting config entry. Therefore it's not suitable to use in integrations which uses connection data, api key's or other information that should be stored in the config entry `data`.
- It may be simpler to use the normal config flow handler if you have extensive validation, setting unique id or checking for duplicated config entries.
- Starting the flow with other steps besides `user` and `import` is discouraged.

```python

from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

async def validate_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options."""
    if user_input[CONF_SOME_SETTING] == "error":
      # 'setup_error' needs to be existing in string.json config errors section
      raise SchemaFlowError("setup_error") 
    return user_input

DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector()
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_SOME_SETTING): TextSelector()
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="options",
    ),
    "options": SchemaFlowFormStep(
        schema=DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_setup,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_setup,
    ),
}

class MyConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True # Reload without a config entry listener

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title from input."""
        return cast(str, options[CONF_NAME])

```

## Testing your config flow

Integrations with a config flow require full test coverage of all code in `config_flow.py` to be accepted into core. [Test your code](development_testing.md#running-a-limited-test-suite) includes more details on how to generate a coverage report.

---
title: "Multi-factor authentication modules"
---

Multi-factor Authentication Modules are used in conjunction with [Authentication Provider](auth_auth_provider.md) to provide a fully configurable authentication framework. Each MFA module may provide one multi-factor authentication function. User can enable multiple mfa modules, but can only select one module in login process.

## Defining an mfa auth module

:::info
We currently only support built-in mfa auth modules. Support for custom auth modules might arrive in the future.
:::

Multi-factor Auth modules are defined in `homeassistant/auth/mfa_modules/<name of module>.py`. The auth module will need to provide an implementation of the `MultiFactorAuthModule` class.

For an example of a fully implemented auth module, please see [insecure_example.py](https://github.com/home-assistant/core/blob/dev/homeassistant/auth/mfa_modules/insecure_example.py).

Multi-factor Auth modules shall extend the following methods of `MultiFactorAuthModule` class.

| method | Required | Description
| ------ | -------- | -----------
| `@property def input_schema(self)` | Yes | Return a schema defined the user input form.
| `async def async_setup_flow(self, user_id)` | Yes | Return a SetupFlow to handle the setup workflow.
| `async def async_setup_user(self, user_id, setup_data)` | Yes | Set up user for use this auth module.
| `async def async_depose_user(self, user_id)` | Yes | Remove user information from this auth module.
| `async def async_is_user_setup(self, user_id)` | Yes | Return whether user is set up.
| `async def async_validate(self, user_id, user_input)` | Yes | Given a user_id and user input, return validation result.
| `async def async_initialize_login_mfa_step(self, user_id)` | No | Will be called once before display the mfa step of login flow. This is not initialization for the MFA module but the mfa step in login flow.

## Setup flow

Before user can use a multi-factor auth module, it has to be enabled or set up. All available modules will be listed in user profile page, user can enable the module he/she wants to use. A setup data entry flow will guide user finish the necessary steps.

Each MFA module need to implement a setup flow handler extends from `mfa_modules.SetupFlow` (if only one simple setup step need, `SetupFlow` can be used as well). For example for Google Authenticator (TOTP, Time-based One Time Password) module, the flow will need to be:

- Generate a secret and store it on instance of setup flow
- Return `async_show_form` with a QR code in the description (injected as base64 via `description_placeholders`)
- User scans code and enters a code to verify it scanned correctly and clock in synced
- TOTP module saved the secret along with user_id, module is enabled for user

## Workflow

<img class='invertDark' src='/img/en/auth/mfa_workflow.png'
  alt='Multi Factor Authentication Workflow' />

<!--
Source: https://drive.google.com/file/d/12_nANmOYnOdqM56BND01nPjJmGXe-M9a/view
-->

## Configuration example

```yaml
# configuration.xml
homeassistant:
  auth_providers:
    - type: homeassistant
    - type: legacy_api_password
  auth_mfa_modules:
    - type: totp
    - type: insecure_example
      users: [{'user_id': 'a_32_bytes_length_user_id', 'pin': '123456'}]
```

In this example, user will first select from `homeassistant` or `legacy_api_password` auth provider. For `homeassistant` auth provider, user will first input username/password, if that user enabled both `totp` and `insecure_example`, then user need select one auth module, then input Google Authenticator code or input pin code base on the selection.

:::tip
`insecure_example` is only for demo purpose, please do not use it in production.
:::

## Validation session

Not like auth provider, auth module use session to manage the validation. After auth provider validated, mfa module will create a validation session, include an expiration time and user_id from auth provider validate result. Multi-factor auth module will not only verify the user input, but also verify the session is not expired. The validation session data is stored in your configuration directory.

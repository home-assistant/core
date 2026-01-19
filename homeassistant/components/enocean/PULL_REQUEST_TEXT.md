<!--
  You are amazing! Thanks for contributing to our project!
  Please, DO NOT DELETE ANY TEXT from this template! (unless instructed).
-->
## Breaking change
<!--
  If your PR contains a breaking change for existing users, it is important
  to tell them what breaks, how to make it work again and why we did this.
  This piece of text is published with the release notes, so it helps if you
  write it towards our users, not us.
  Note: Remove this section if this PR is NOT a breaking change.
-->
This is a reimplementation of the EnOcean integration and will **BREAK ANY EXISTING ENOCEAN CONFIGURATION** as the integration's configuration is moved from `configuration.yaml` to UI-based configuration. The documentation (yet to be written!) shall contain pointers on how to manually migrate.

## Proposed change
<!--
  Describe the big picture of your changes here to communicate to the
  maintainers why we should accept this pull request. If it fixes a bug
  or resolves a feature request, be sure to link to that issue in the
  additional information section.
-->
This is a work-in-progress (WIP) reimplementation of the EnOcean integration, using UI-based configuration and several other modern features of Home Assistant like e.g. devices. Moreover, it supports EnOcean-specific features like (UTE) teach-in and EEP-based selection of devices.

While the implementation is not yet completely done, I have decided to open this WIP pull request right now to open up a room for discussion, feedback, suggestions etc. I will continue working on the open items and update this PR accordingly. Given the size of the changes, I expect that this PR will take a longer time until it can be accepted for inclusion. For more information on the background/history of this development, see below.

### Why such a huge PR? Why not split it into small bits?
Simply because I wouldn't know how to split the required work in any meaningful way without having to put a lot of effort into just that. 


### Done
- The entire protocol code is now contained in my [homeassistant-enocean](https://pypi.org/project/homeassistant-enocean/) wrapper library. This library does the "lifting" from the way EnOcean operates (devices having entities) to the way Home Assistant operates (entities that collectively define a device). On the EnOcean side, the library uses EnOcean Equipment Profiles (EEPs) to define the devices features; on the Home Assistant side, it provides the respective platform entities (like covers, lights, sensors, switches etc.). 

- Universal Teach-In (UTE) is supported.

- Most of the integration code (in `homeassistant/components/enocean`) is ready with exceptions as listed in open items below.

- The current state is tested in my own production system and works on a day-to-day basis.

### Open items
Here is what still needs to be done. I've added boxes to the items and - once done - will tick them as completed to document the progress. Also, if additional items come up, I plan to add them to this list here.

- [ ] Create/update the documentation (https://home-assistant.io) - this is most likely the most time-intensive part left
- [ ] Clean up sensor code
- [ ] Shift cover code to the [homeassistant-enocean](https://pypi.org/project/homeassistant-enocean/) library 
- [ ] Ensure sufficient test coverage
- [ ] Screen the open PRs related to EnOcean and check if they require changes to this PR
- [ ] Ensure all the items from this pull request's checklist (see below) are ticked
- [ ] Ensure all the bronze items from the integration quality scale checklist (see below) are ticked
- [ ] Add missing EEPs to support all the devices that used to be supported by the existing integration (nice-to-have)


### Quality scale checklist
Here is the current state as indicated in the ticked boxes. Note that a non-ticked box does not necessarily mean it is not fulfilled, it simply indicates I haven't yet checked it.
#### Bronze
- [x] `action-setup` - Service actions are registered in async_setup
- [x] `appropriate-polling` - If it's a polling integration, set an appropriate polling interval
- [x] `brands` - Has branding assets available for the integration
- [x] `common-modules` - Place common patterns in common modules
- [ ] `config-flow-test-coverage` - Full test coverage for the config flow
- [x] `config-flow` - Integration needs to be able to be set up via the UI
    - [x] Uses `data_description` to give context to fields
    - [ ] Uses `ConfigEntry.data` and `ConfigEntry.options` correctly
- [ ] `dependency-transparency` - Dependency transparency
- [ ] `docs-actions` - The documentation describes the provided service actions that can be used
- [ ] `docs-high-level-description` - The documentation includes a high-level description of the integration brand, product, or service
- [ ] `docs-installation-instructions` - The documentation provides step-by-step installation instructions for the integration, including, if needed, prerequisites
- [ ] `docs-removal-instructions` - The documentation provides removal instructions
- [x] `entity-event-setup` - Entity events are subscribed in the correct lifecycle methods
- [x] `entity-unique-id` - Entities have a unique ID
- [x] `has-entity-name` - Entities use has_entity_name = True
- [x] `runtime-data` - Use ConfigEntry.runtime_data to store runtime data
- [ ] `test-before-configure` - Test a connection in the config flow
- [ ] `test-before-setup` - Check during integration initialization if we are able to set it up correctly
- [x] `unique-config-entry` - Don't allow the same device or service to be able to be set up twice

#### Silver
- [x] `action-exceptions` - Service actions raise exceptions when encountering failures
- [x] `config-entry-unloading` - Support config entry unloading
- [ ] `docs-configuration-parameters` - The documentation describes all integration configuration options
- [ ] `docs-installation-parameters` - The documentation describes all integration installation parameters
- [ ] `entity-unavailable` - Mark entity unavailable if appropriate
- [ ] `integration-owner` - Has an integration owner
- [ ] `log-when-unavailable` - If internet/device/service is unavailable, log once when unavailable and once when back connected
- [ ] `parallel-updates` - Number of parallel updates is specified
- [ ] `reauthentication-flow` - Reauthentication needs to be available via the UI
- [ ] `test-coverage` - Above 95% test coverage for all integration modules

#### Gold
- [x] `devices` - The integration creates devices
- [ ] `diagnostics` - Implements diagnostics
- [ ] `discovery-update-info` - Integration uses discovery info to update network information
- [ ] `discovery` - Devices can be discovered
- [ ] `docs-data-update` - The documentation describes how data is updated
- [ ] `docs-examples` - The documentation provides automation examples the user can use.
- [ ] `docs-known-limitations` - The documentation describes known limitations of the integration (not to be confused with bugs)
- [ ] `docs-supported-devices` - The documentation describes known supported / unsupported devices
- [ ] `docs-supported-functions` - The documentation describes the supported functionality, including entities, and platforms
- [ ] `docs-troubleshooting` - The documentation provides troubleshooting information
- [ ] `docs-use-cases` - The documentation describes use cases to illustrate how this integration can be used
- [ ] `dynamic-devices` - Devices added after integration setup
- [ ] `entity-category` - Entities are assigned an appropriate EntityCategory
- [ ] `entity-device-class` - Entities use device classes where possible
- [ ] `entity-disabled-by-default` - Integration disables less popular (or noisy) entities
- [ ] `entity-translations` - Entities have translated names
- [ ] `exception-translations` - Exception messages are translatable
- [ ] `icon-translations` - Entities implement icon translations
- [ ] `reconfiguration-flow` - Integrations should have a reconfigure flow
- [ ] `repair-issues` - Repair issues and repair flows are used when user intervention is needed
- [ ] `stale-devices` - Stale devices are removed

#### Platinum
- [ ] `async-dependency` - Dependency is async
- [ ] `inject-websession` - The integration dependency supports passing in a websession
- [ ] `strict-typing` - Strict typing

### Background/history
The trigger for this effort was my [previous attempt (PR #75356)](https://github.com/home-assistant/core/pull/75356) to *add support for EnOcean cover (roller shutters based on EEP D2-05-00)* back in 2022, which was declined. Two reasons were given, namely that

1. the EnOcean protocol specific code present in the code had to be moved to an external lib, and
2. that it was no longer allowed for integrations to add or change a platform YAML configuration (see the respective [ADR 0007](ttps://github.com/home-assistant/architecture/blob/master/adr/0007-integration-config-yaml-structure.md#decision)). 

When digging into this, I stumbled also across [ADR 0010](https://github.com/home-assistant/architecture/blob/master/adr/0010-integration-configuration.md), requiring *"Integrations that communicate with devices and/or services are only configured via the UI. In rare cases, we can make an exception".* 


## Type of change
<!--
  What type of change does your PR introduce to Home Assistant?
  NOTE: Please, check only 1! box!
  If your PR requires multiple boxes to be checked, you'll most likely need to
  split it into multiple PRs. This makes things easier and faster to code review.
-->

- [ ] Dependency upgrade
- [ ] Bugfix (non-breaking change which fixes an issue)
- [ ] New integration (thank you!)
- [ ] New feature (which adds functionality to an existing integration)
- [ ] Deprecation (breaking change to happen in the future)
- [x] Breaking change (fix/feature causing existing functionality to break)
- [ ] Code quality improvements to existing code or addition of tests

## Additional information
<!--
  Details are important, and help maintainers processing your PR.
  Please be sure to fill out additional details, if applicable.
-->

- This PR fixes or closes issue: fixes #
- This PR is related to issue: 
- Link to documentation pull request: 
- Link to developer documentation pull request: 
- Link to frontend pull request: 

## Checklist
<!--
  Put an `x` in the boxes that apply. You can also fill these out after
  creating the PR. If you're unsure about any of them, don't hesitate to ask.
  We're here to help! This is simply a reminder of what we are going to look
  for before merging your code.

  AI tools are welcome, but contributors are responsible for *fully*
  understanding the code before submitting a PR.
-->

- [x] I understand the code I am submitting and can explain how it works.
- [x] The code change is tested and works locally.
- [ ] Local tests pass. **Your PR cannot be merged unless tests pass**
- [ ] There is no commented out code in this PR.
- [ ] I have followed the [development checklist][dev-checklist]
- [ ] I have followed the [perfect PR recommendations][perfect-pr]
- [x] The code has been formatted using Ruff (`ruff format homeassistant tests`)
- [ ] Tests have been added to verify that the new code works.
- [x] Any generated code has been carefully reviewed for correctness and compliance with project standards.

If user exposed functionality or configuration variables are added/changed:

- [ ] Documentation added/updated for [www.home-assistant.io][docs-repository]

If the code communicates with devices, web services, or third-party tools:

- [ ] The [manifest file][manifest-docs] has all fields filled out correctly.  
      Updated and included derived files by running: `python3 -m script.hassfest`.
- [x] New or updated dependencies have been added to `requirements_all.txt`.  
      Updated by running `python3 -m script.gen_requirements_all`.
- [ ] For the updated dependencies - a link to the changelog, or at minimum a diff between library versions is added to the PR description.

<!--
  This project is very active and we have a high turnover of pull requests.

  Unfortunately, the number of incoming pull requests is higher than what our
  reviewers can review and merge so there is a long backlog of pull requests
  waiting for review. You can help here!
  
  By reviewing another pull request, you will help raise the code quality of
  that pull request and the final review will be faster. This way the general
  pace of pull request reviews will go up and your wait time will go down.
  
  When picking a pull request to review, try to choose one that hasn't yet
  been reviewed.

  Thanks for helping out!
-->

To help with the load of incoming pull requests:

- [ ] I have reviewed two other [open pull requests][prs] in this repository.

[prs]: https://github.com/home-assistant/core/pulls?q=is%3Aopen+is%3Apr+-author%3A%40me+-draft%3Atrue+-label%3Awaiting-for-upstream+sort%3Acreated-desc+review%3Anone+-status%3Afailure

<!--
  Thank you for contributing <3

  Below, some useful links you could explore:
-->
[dev-checklist]: https://developers.home-assistant.io/docs/development_checklist/
[manifest-docs]: https://developers.home-assistant.io/docs/creating_integration_manifest/
[quality-scale]: https://developers.home-assistant.io/docs/integration_quality_scale_index/
[docs-repository]: https://github.com/home-assistant/home-assistant.io
[perfect-pr]: https://developers.home-assistant.io/docs/review-process/#creating-the-perfect-pr

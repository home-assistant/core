---
title: "Checklist for creating a component"
sidebar_label: Component checklist
---

A checklist of things to do when you're adding a new component.

:::info
Not all existing code follows the requirements in this checklist. This cannot be used as a reason to not follow them!
:::

### 0. Common

 1. Follow our [Style guidelines](development_guidelines.md)
 2. Use existing constants from [`const.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/const.py)
    - Only add new constants to `const.py` if they are widely used. Otherwise keep them on components level

### 1. External requirements

 1. Requirements have been added to [`manifest.json`](creating_integration_manifest.md). The `REQUIREMENTS` constant is deprecated.
 2. Requirement version must be pinned: `"requirements": ['phue==0.8.1']`
 4. Each requirement meets the [library requirements](api_lib_index.md#basic-library-requirements).

### 2. Configuration

1. Voluptuous schema present for [configuration validation](development_validation.md)
2. Default parameters specified in voluptuous schema, not in `setup(…)`
3. Schema using as many generic config keys as possible from `homeassistant.const`
4. If your component has platforms, define a `PLATFORM_SCHEMA` instead of a `CONFIG_SCHEMA`.
5. If using a `PLATFORM_SCHEMA` to be used with `EntityComponent`, import base from `homeassistant.helpers.config_validation`
6. Never depend on users adding things to `customize` to configure behavior inside your component.

### 3. Component/platform communication

1. You can share data with your platforms by leveraging `hass.data[DOMAIN]`.
2. If the component fetches data that causes its related platform entities to update, you can notify them using the dispatcher code in `homeassistant.helpers.dispatcher`.

### 4. Communication with devices/services

1. All API specific code has to be part of a third party library hosted on PyPi. Home Assistant should only interact with objects and not make direct calls to the API.

    ```python
    # bad
    status = requests.get(url("/status"))
    # good
    from phue import Bridge

    bridge = Bridge(...)
    status = bridge.status()
    ```

    [Tutorial on publishing your own PyPI package](https://towardsdatascience.com/how-to-open-source-your-first-python-package-e717444e1da0)
    
    Other noteworthy resources for publishing python packages:  
    [Cookiecutter Project](https://cookiecutter.readthedocs.io/)  
    [flit](https://flit.readthedocs.io/)  
    [Poetry](https://python-poetry.org/)  

### 5. Make your pull request as small as possible

Keep a new integration to the minimum functionality needed for someone to get value out of the integration. This allows reviewers to sign off on smaller chunks of code one at a time, and lets us get your new integration/features in sooner. **Pull requests containing large code dumps will not be a priority for review and may be closed.**

- Limit to a single platform
- Do not add features not needed to directly support the single platform (such as custom service actions)
- Do not mix clean-ups and new features in a single pull request.
- Do not solve several issues in a single pull request.
- Do not submit pull requests that depend on other work which is still unmerged.

It may be tempting to open a large PR when "modernizing" an integration that hasn't been touched in a while to take advantage of all the latest features available. The right approach is to break the features down into independent functional changes as best you can and to submit the PRs sequentially.

One strategy for handling sequential PRs is to create a branch for the `next` PR off the `current` PR's branch, which you can then start writing code against. This strategy is advantageous if you have split up the PRs such that one is dependent on the previous one since you are working off of the code that will be in `dev` once the PR is merged. If you add additional commits to the `current` PR because of changes/review feedback, you can rebase your `next` PR's branch and more easily incorporate any merge conflicts. Once your `current` PR has been merged, squash the commits from the `current` PR branch in the `next` PR branch and then rebase on `dev`. Then you can submit your `next` PR branch for review and rinse and repeat as needed.

### 6. Event names

Prefix component event names with the domain name. For example, use `netatmo_person` instead of `person` for the `netatmo` component. Please be mindful of the data structure as documented on our [Data Science portal](https://data.home-assistant.io/docs/events/#database-table).

### 7. Tests

Strongly consider adding tests for your component to minimize future regressions.

## Description:


**Related issue (if applicable):** fixes #<home-assistant issue number goes here>

**Pull request in [home-assistant.github.io](https://github.com/home-assistant/home-assistant.github.io) with documentation (if applicable):** home-assistant/home-assistant.github.io#<home-assistant.github.io PR number goes here>

## Example entry for `configuration.yaml` (if applicable):
```yaml

```

## Checklist:
  - [ ] The code change is tested and works locally.
  - [ ] Local tests pass with `tox`. **Your PR cannot be merged unless tests pass**

If user exposed functionality or configuration variables are added/changed:
  - [ ] Documentation added/updated in [home-assistant.github.io](https://github.com/home-assistant/home-assistant.github.io)

If the code communicates with devices, web services, or third-party tools:
  - [ ] New dependencies have been added to the `REQUIREMENTS` variable ([example][ex-requir]).
  - [ ] New dependencies are only imported inside functions that use them ([example][ex-import]).
  - [ ] New dependencies have been added to `requirements_all.txt` by running `script/gen_requirements_all.py`.
  - [ ] New files were added to `.coveragerc`.

If the code does not interact with devices:
  - [ ] Tests have been added to verify that the new code works.

[ex-requir]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/keyboard.py#L14
[ex-import]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/keyboard.py#L54

## Breaking Change:

<!-- What is breaking and why we have to break it. Remove this section only if it was NOT a breaking change. -->

## Description:


**Related issue (if applicable):** fixes #<home-assistant issue number goes here>

**Pull request in [home-assistant.io](https://github.com/home-assistant/home-assistant.io) with documentation (if applicable):** home-assistant/home-assistant.io#<home-assistant.io PR number goes here>

## Example entry for `configuration.yaml` (if applicable):
```yaml

```

## Checklist:
  - [ ] The code change is tested and works locally.
  - [ ] Local tests pass with `tox`. **Your PR cannot be merged unless tests pass**
  - [ ] There is no commented out code in this PR.

If user exposed functionality or configuration variables are added/changed:
  - [ ] Documentation added/updated in [home-assistant.io](https://github.com/home-assistant/home-assistant.io)

If the code communicates with devices, web services, or third-party tools:
  - [ ] [_The manifest file_][manifest-docs] has all fields filled out correctly ([example][ex-manifest]).
  - [ ] New dependencies have been added to `requirements` in the manifest ([example][ex-requir]).
  - [ ] New dependencies are only imported inside functions that use them ([example][ex-import]).
  - [ ] New or updated dependencies have been added to `requirements_all.txt` by running `script/gen_requirements_all.py`.
  - [ ] New files were added to `.coveragerc`.

If the code does not interact with devices:
  - [ ] Tests have been added to verify that the new code works.

[ex-manifest]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/mobile_app/manifest.json
[ex-requir]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/mobile_app/manifest.json#L5
[ex-import]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/keyboard/__init__.py#L23
[manifest-docs]: https://developers.home-assistant.io/docs/en/development_checklist.html#_the-manifest-file_

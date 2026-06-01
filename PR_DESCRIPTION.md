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


## Proposed change
<!--
  Describe the big picture of your changes here to communicate to the
  maintainers why we should accept this pull request. If it fixes a bug
  or resolves a feature request, be sure to link to that issue in the
  additional information section.
-->

Adds a `cover` platform to the Fluss+ integration so devices with a
position sensor are exposed as a garage door / gate cover instead of a
button. Builds on the per-device status fetch from #168154.

The dispatch is decided once per device at platform setup, based on
whether the API returns `openCloseStatus`. Devices that report it become a
`CoverEntity` (`CoverDeviceClass.GARAGE`, `OPEN | CLOSE`) and gain
explicit open/close commands plus open/closed state. Devices that don't
report it keep the existing button — the two are mutually exclusive per
device, so no user with an existing button setup loses anything.

Open and close go through the library's `async_open_device` /
`async_close_device` and end with `coordinator.async_request_refresh()`,
so state in the UI reflects the new position immediately rather than
waiting for the next 30 minute coordinator cycle. Library failures
translate to `HomeAssistantError` via `open_failed` / `close_failed`
translation keys.

Cover and button share the same coordinator, so we still make exactly one
status call per device per refresh — the existing
`_async_get_connectivity` helper is generalised to return the full
status payload, keeping connectivity behaviour and feeding `openCloseStatus`
to the cover from the same data.

While here, the coordinator is moved to a typed `FlussDevice` dataclass
(`dict[str, FlussDevice]`) instead of `dict[str, dict[str, Any]]`, matching
the pattern in newer Platinum integrations like `peblar`, `airgradient`,
`airos`, `airobot`, and `apcupsd`. snake_case fields throughout; camelCase
conversion happens at the coordinator boundary.

`openCloseStatus` is parsed defensively for both the documented boolean
shape and the example-payload string shape — `"Closed"` / `"Open"`
(case-insensitive) and `True` / `False` both map correctly. Verified
locally against a real Fluss+ device.

100% test coverage on every fluss file (31 tests). `ruff`, `hassfest`,
and `mypy` clean.

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
- [x] New feature (which adds functionality to an existing integration)
- [ ] Deprecation (breaking change to happen in the future)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Code quality improvements to existing code or addition of tests

## Additional information
<!--
  Details are important, and help maintainers processing your PR.
  Please be sure to fill out additional details, if applicable.
-->

- This PR is related to issue: #168154
- Documentation pull request to follow at home-assistant/home-assistant.io
  once this lands.

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
- [x] Local tests pass. **Your PR cannot be merged unless tests pass**
- [x] There is no commented out code in this PR.
- [x] I have followed the [development checklist][dev-checklist]
- [x] I have followed the [perfect PR recommendations][perfect-pr]
- [x] The code has been formatted using Ruff (`ruff format homeassistant tests`)
- [x] Tests have been added to verify that the new code works.
- [x] Any generated code has been carefully reviewed for correctness and compliance with project standards.

If user exposed functionality or configuration variables are added/changed:

- [ ] Documentation added/updated for [www.home-assistant.io][docs-repository]

If the code communicates with devices, web services, or third-party tools:

- [x] The [manifest file][manifest-docs] has all fields filled out correctly.  
      Updated and included derived files by running: `python3 -m script.hassfest`.
- [ ] New or updated dependencies have been added to `requirements_all.txt`.  
      Updated by running `python3 -m script.gen_requirements_all`.
- [ ] For the updated dependencies a diff between library versions and ideally a link to the changelog/release notes is added to the PR description.

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

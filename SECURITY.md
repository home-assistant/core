# Security Policy

## Supported Versions

Only the latest stable or official release of Home Assistant is supported with security fixes. Development (`dev`) and beta releases are evaluated on a case-by-case basis. No forks or community builds are covered.

| Version | Supported |
|---------|-----------|
| Latest stable release | :white_check_mark: |
| Development / beta | :white_check_mark: (case-by-case) |
| Older releases | :x: |
| Forks | :x: |

## Reporting a Vulnerability

**Do not** report security vulnerabilities through public GitHub issues, discussions, or pull requests. Use the private channels below.

### Primary Channel: GitHub Security Advisory

Report vulnerabilities directly via the GitHub Security Advisory feature:

[https://github.com/home-assistant/core/security/advisories/new](https://github.com/home-assistant/core/security/advisories/new)

### Press and Researcher Inquiries

If you are writing about Home Assistant security or need to confirm claims, contact us at [hello@home-assistant.io](mailto:hello@home-assistant.io).

### What to Include

When reporting, please provide:

- The affected version(s), tag(s), or commit SHA(s)
- A description of the issue and why you believe it is security-sensitive
- Steps to reproduce or a proof of concept
- Any relevant logs, payloads, or screenshots
- The potential impact
- A [CVSS 3.1](https://www.first.org/cvss/v3.1/specification-document) vector string if you are familiar with the scoring system (use the [calculator](https://www.first.org/cvss/calculator/3.1))

## Response Expectations

Home Assistant is a volunteer-run project. You can expect:

1. **Acknowledgment** within 7 business days of submitting a report
2. **Assessment and follow-up** after initial review
3. **At least 90 days** from acknowledgment to release a fix, during which we will keep you informed of progress

## Non-Qualifying Vulnerabilities

We do **not** accept reports for:

- Automated tool or scanner results
- Theoretical attacks without proof of exploitability
- Third-party library issues (report those to the library maintainer)
- Social engineering attacks
- Attacks that require host system access
- Attacks requiring physical access or relying on already-compromised devices or networks (e.g., man-in-the-middle on an untrusted network)
- Malicious third-party software (custom integrations, apps, plugins)
- Attacks a user can only perform against their own setup
- Privilege escalation — all authenticated users are trusted and have the same access as the owner (see [documentation](https://www.home-assistant.io/docs/authentication/#user-accounts))

## Disclosure & CVE Assignment

Valid, non-public vulnerabilities in Home Assistant itself with a severity of **medium or higher** will receive:

- A **GitHub Security Advisory** published on this repository
- A **CVE identifier** assigned

Disclosure timing is coordinated with the reporter when appropriate.

## Bounties

Home Assistant cannot offer financial bounties. Discoverers will be credited in the advisory and release notes.

## Full Policy

See [https://www.home-assistant.io/security/](https://www.home-assistant.io/security/) for the complete security policy and a list of past advisories.

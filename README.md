# tripwire

Detects changes in your Eero network — new, missing, renamed, or regrouped devices —
by comparing the current state against a baseline you save.

## Installation

```bash
git clone <this repo>
cd tripwire
uv sync
```

This installs the `tripwire` command into `.venv/`. Run it with `uv run tripwire ...`,
or activate the virtualenv (`source .venv/bin/activate`) to run `tripwire ...` directly.

## Quick start

```bash
tripwire login you@example.com          # or a phone number
tripwire verify 123456                  # the code Eero sent you
tripwire init --baseline network.json   # save the current state as a baseline

# ... later, or after changing something on your network ...

tripwire check --baseline network.json  # compare current state to the baseline
tripwire update --baseline network.json # accept the current state as the new baseline
```

## Command reference

| Command | Flags | What it does | Exit codes |
|---|---|---|---|
| `tripwire login <identifier>` | | Requests a verification code by email or phone. | `0` requested, `1` error |
| `tripwire verify <code>` | | Completes login with the code you received. | `0` logged in, `1` error |
| `tripwire logout` | | Revokes and clears the stored session. | `0` success, `1` error |
| `tripwire init` | `--baseline PATH` (required), `--force` | Creates a new baseline from a live scan. Refuses to overwrite an existing file unless `--force` is given. | `0` success, `1` error |
| `tripwire update` | `--baseline PATH` (required) | Refreshes an existing baseline from a live scan. Fails if the file doesn't exist yet (`init` it first). | `0` success, `1` error |
| `tripwire check` | `--baseline PATH` (required), `--json` | Compares the current state to the baseline and prints what changed, grouped by Added/Removed/Renamed/Changed/Regrouped. `--json` prints a single JSON document instead of text. | `0` no changes, `1` changes found, `2` error |

`check`'s three-way exit code lets you script on it directly, e.g. in a cron job or
CI step: `tripwire check --baseline network.json || notify-me`.

## Risks: undocumented Eero API

tripwire talks to Eero through [`eero-api`](https://pypi.org/project/eero-api/), a
reverse-engineered client for Eero's unofficial app API. Everything behind the
`EeroAdapter` boundary (`src/tripwire/eero_adapter.py`) is subject to:

- **Endpoint changes**: Eero can add, remove, or reshape endpoints without notice.
- **Auth breakage**: the email/phone verification flow can change shape or move hosts.
- **Response drift**: field names, types, or nesting in the raw JSON envelopes can
  shift between account types or app versions.
- **Unclear throttling**: there is no published rate limit; aggressive polling risks
  silent throttling or account lockout.

**Fallback threshold**: replace `eero-api` with a minimal local implementation if any
of the following happen: it goes unmaintained (no release or fix for a breaking change
within ~60 days), it drops support for the Python versions tripwire targets, or a
breaking API change surfaces that only `eero-api`'s internals (not the `EeroAdapter`
interface) need to absorb. Because scanner and CLI code only depend on `EeroAdapter`,
replacing the client under it should not require changes outside
`src/tripwire/eero_adapter.py`.

## Security limitations

tripwire is a **change detector**, not a preventive control. Understand what that
does and doesn't mean before relying on it:

- **It only reports drift it can see through Eero's app API.** If the API doesn't
  expose a piece of state (or an attacker's action doesn't change anything the API
  reports), tripwire won't see it either. See "Risks: undocumented Eero API" above
  for the API's own reliability limits.
- **It does not block, quarantine, or remove anything.** `check` only reports; it
  never pauses a device, changes a password, or otherwise acts on your network.
  Responding to a reported change is entirely up to you.
- **Baseline files are unsigned plain JSON.** Anyone with filesystem access to a
  baseline file can edit it — including editing it to make a rogue device look like
  it was always there, hiding it from future `check` runs. tripwire does not detect
  or prevent tampering with its own baseline. Protect the baseline file the way you'd
  protect any other sensitive local file (e.g. filesystem permissions); there is no
  signing or encryption in this version.
- **A compromised session token is close to as powerful as your own login.** The
  token stored in your OS keyring (see below) can read your network's full device
  list and settings, and `eero-api` exposes methods that can change the account's
  name, email, or phone number. There's no exposed method to change the account's
  password or billing details, but treat this token with the same care as your Eero
  login itself.

## Authentication and credential storage

```bash
tripwire login <email-or-phone>   # requests a verification code
tripwire verify <code>            # completes login with the code you received
tripwire logout                   # revokes and clears the stored session
```

Credentials are never written to any file tracked by this repository. The session
token is persisted by `eero-api`'s own storage, in priority order:

1. **OS keyring** (service `eero-api`, account `auth-tokens`) via the `keyring`
   package — the Secret Service / GNOME Keyring or KWallet on Linux, Keychain on
   macOS, Credential Manager on Windows. This is used whenever a keyring backend is
   available, which is the common case.
2. **Fallback file** at `~/.tripwire/session`, used only if the keyring write fails.

**To revoke access**, run `tripwire logout`, which clears both the keyring entry and
the fallback file. If you lose access to the CLI, you can instead:

- revoke the session directly from your OS's keyring/credential manager (look for the
  `eero-api` entry), or
- delete `~/.tripwire/session` if a fallback file exists, or
- sign out of the account from the Eero app, which invalidates the session
  server-side regardless of what tripwire has stored locally.

## Baseline format

A baseline is plain JSON, safe to inspect, `git diff`, or query with `jq` — there's
nothing opaque or binary in it. `tripwire init`/`update` write it; `tripwire check`
only reads it, never writes.

Top level:

```json
{
  "schema_version": 1,
  "network": { "id": "...", "name": "...", "status": "..." },
  "nodes": [ { "id": "...", "serial": "...", "location": "...", "model": "...",
               "mac_address": "...", "ip_address": "...", "is_primary": true,
               "is_gateway": true, "status": "..." } ],
  "profiles": [ { "id": "...", "name": "...", "is_default": false } ],
  "devices": [ { "mac": "...", "nickname": "...", "hostname": "...",
                 "display_name": "...", "connected": true, "wireless": true,
                 "connection_type": "...", "node_id": "...", "node_location": "...",
                 "manufacturer": "...", "ip": "...", "is_guest": false,
                 "paused": false, "group": "..." } ]
}
```

`devices[].group` is the device's Eero profile name, or the literal string
`"Ungrouped"` for a device with no profile assignment.

**Compatibility**: `schema_version` identifies the exact shape above. There is no
migration between versions yet — `tripwire check`/`update` raise a clear error on a
baseline written by a different (or missing) `schema_version` rather than guessing at
its structure. If this file's shape ever needs to change, `schema_version` is what
future tripwire versions will key off of to decide whether (and how) to read it.

## Development

```bash
uv sync --extra test
uv run pytest
uv run tripwire --help
```

# Changelog

All notable changes to the Railhead Python SDK are tracked here.

## 0.2.0 - Builder Preview

Release status: prepared locally; public sync/publish is blocked on the SDK Git
history cleanup/rotation decision documented in `../codex-security-scan.md`.

### Added

- `railhead init --invite-code ...` onboarding flow that generates a wallet,
  redeems faucet funding, writes credentials with `0600` permissions, and
  creates a starter `agent.py`.
- `RailheadClient.from_credentials()` for loading credentials created by
  `railhead init`.
- SDK input relay support through `/job-inputs/{job_id}` so off-VPS agents can
  receive job payloads.
- SDK result-body retrieval through `/job-results/{job_id}` when waiting for a
  completed job.
- CLI commands for status, capabilities, agents, jobs, and posting jobs.
- Cleaner examples that require environment/config credentials instead of
  hardcoded keys.

### Changed

- Agent examples now use `endpoint="polling"` to match alpha job delivery.
- Job status mapping now matches the live `JobMarket.sol` enum:
  `Open`, `Accepted`, `Complete`, `Disputed`, `Cancelled`, `Expired`.
- README install guidance now treats GitHub as the source of truth until PyPI
  publication is confirmed.

### Security

- Removed executable hardcoded private keys from current tracked examples.
- Public release remains blocked until historical secret-shaped values in SDK
  Git history are resolved or explicitly accepted as inert/redacted.

## 0.1.0 - Initial SDK

- Initial Python SDK package with client, agent, chain, types, and CLI surfaces.

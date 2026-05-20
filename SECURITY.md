# Security policy

`opentele-ng` accepts attacker-influenced binary blobs (tdata files from
the filesystem and Telegram-server responses through Telethon). Any class
of bug that lets a crafted input do one of the following is in scope:

- **Remote code execution** in the importer / parser
- **Unbounded memory / CPU** (`OOM`, DoS) on malformed payloads
- **Path traversal** in `tdata` write code
- **Authentication-bypass** through tampered `auth_key` / `salt`
- **Information disclosure** of secrets from process memory or logs

## Supported versions

| Version | Status |
|---------|--------|
| 1.0.3 and later | Active — security fixes go here |
| 1.0.x earlier | EOL — please upgrade; 1.0.3 closed all known DoS vectors |
| 0.x | EOL — major dependency surface change in 1.0.0 |

## Reporting a vulnerability

**Do not open a public GitHub issue for a security report.**

Email the maintainer privately at the address in
[`setup.py:author_email`](setup.py), or open a
[GitHub Security Advisory](https://github.com/stufently/opentele/security/advisories/new)
for this repo.

What to include:

- A clear description of the vulnerability and the affected version
  (`pip show opentele-ng` output works).
- A minimal reproducer: a Python snippet plus a hex-encoded byte string
  for the malformed payload, or a small `tdata`-shaped folder.
- The impact you observed (process hang, OOM kill, traceback, etc.).
- Optional: a suggested fix or patch.

## What to expect

- **Acknowledgement** within 3 business days.
- **Triage** within 14 days. Severity is assigned using a simple
  judgement of impact × exploit difficulty — there is no formal
  CVSS scoring.
- **Coordinated disclosure** for confirmed vulnerabilities: a fix lands
  in the next patch release (e.g. `1.0.x → 1.0.x+1`), the CHANGELOG
  describes the vulnerability after the release is out, and credit is
  given by name (or anonymously, your choice).

## Known hardenings already in place

- **DoS guards** (1.0.3) on every attacker-controlled `count` loop in
  `MapData.read` (lskDraft / lskDraftPosition / lskLegacyImages /
  lskBotStorages), `Account._setMtpAuthorization.readKeys`, and
  `TDesktop.__loadFromTData` accounts list. Pre-loop cap by
  `bytesAvailable() // pair_size`. See `tests/test_dos_protection.py`.
- **OOM protection** (1.0.2) on `QByteArray` / `QString` deserialization:
  a declared length of `0xFFFFFFFE` (~4 GB) on a short payload sets
  `Status.ReadPastEnd` instead of pre-allocating. See
  `tests/qdatastream/test_pure_errors.py`.
- **AES alignment** (1.0.1) on the encrypted descriptor empty-payload
  path: writes the minimal valid upstream-readable `dataLen=4` size
  marker and pads to a 16-byte AES block, instead of trying to encrypt
  a 0-byte payload (which would fail with `tgcrypto`'s "data must be
  multiple of 16 bytes").
- **Status sticky** in `opentele.td.qdatastream.QDataStream`:
  `ReadPastEnd` / `ReadCorruptData` persist across reads until
  `resetStatus()` — matches PyQt6 semantics, prevents masking of
  earlier corruption by a subsequent successful read.
- **`@extend_class` strict by default** (3.0+): attribute conflicts
  raise `TypeError` instead of silently dropping the attribute. Set
  `OPENTELE_EXTEND_STRICT=0` to fall back to the warning-only behaviour
  for upstream compatibility, but this widens the attack surface for
  malicious extensions and is not recommended for production.

## Out of scope

- Vulnerabilities in `telethon`, `tgcrypto-pyrofork`, or other third-party
  dependencies — please report those upstream.
- Issues that require an attacker to already have write access to your
  tdata folder (the entire model assumes that folder is a trust
  boundary).
- Bugs in unofficial Telegram clients whose tdata format `opentele-ng`
  cannot guarantee to read correctly. Submit a separate compatibility
  issue.

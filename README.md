# agyred

Multi-account CLI for [Antigravity](https://antigravity.google/) products:

- **Antigravity CLI** (`agy`)
- **Antigravity IDE**
- **Antigravity** desktop

Manage Google accounts, quotas, and session switching from a single static binary. Own encrypted local store — no other apps required for login or account management.

**Module:** [`github.com/ala2524/agyred`](https://github.com/ala2524/agyred)  
*(Maintained by [@ala2524](https://github.com/ala2524), based on `agm`)*

---

## Install

```bash
go install github.com/ala2524/agyred@latest
```

Or from a clone of this repository:

```bash
git clone https://github.com/ala2524/agyred.git
cd agyred
go build -o agyred .
# optional: install to PATH
cp agyred ~/.local/bin/agyred
```

Requires **Go 1.22+** to build. Runs on **macOS**, **Linux**, and **Windows**.

```bash
agyred help
```

*(Note: `agm` is registered as a command alias for complete backward compatibility)*

### Environment

| Variable | Purpose |
|----------|---------|
| `AGYRED_DATA_DIR` | Data directory (default `~/.antigravity-agent`) |
| `AGYRED_DB_PATH` | Full path to `cloud_accounts.db` |
| `AGM_DATA_DIR` | Backward-compatible alias for `AGYRED_DATA_DIR` |
| `AGM_DB_PATH` | Backward-compatible alias for `AGYRED_DB_PATH` |
| `ANTIGRAVITY_AGENT_DIR` | Legacy alias for agent data directory |

---

## Quick start

```bash
agyred init                          # create local store (also automatic)
agyred login                         # add a Google account via browser OAuth
agyred list
agyred switch you@gmail.com --target agy
```

---

## Adding accounts

### Browser OAuth (recommended)

```bash
agyred login
# alias: agyred add
```

1. Listens on `http://localhost:8888` (falls back through `8892` if busy)
2. Opens the browser for Google consent (offline access + refresh token)
3. Stores encrypted tokens and a quota snapshot locally

Run once per Google account.

### Import an existing Antigravity session

| Command | Source |
|---------|--------|
| `agyred import-cli` | OS credential store used by **agy** |
| `agyred import-ide` | Antigravity IDE `state.vscdb` |

Imports the **currently active** session only. For additional accounts, use `agyred login` or switch the product session and import again.

### Backup / restore

```bash
agyred export accounts_backup.json
agyred import-backup accounts_backup.json
```

Exports keep fields **encrypted**. Restoring on another machine needs the same master key (`.mk`). Prefer `agyred login` on a fresh machine.

---

## Switching accounts

```bash
agyred switch <email|alias|partial> [--target agy|ide|all]
```

| Target | Product | Behavior |
|--------|---------|----------|
| `agy` (`cli`) | Antigravity CLI | Write OS credential store only (no GUI process restart) |
| `ide` | Antigravity IDE | Inject OAuth into `state.vscdb`, restart IDE if found |
| `all` (default) | All surfaces | Applies `agy` → `ide` |

```bash
agyred switch work --target agy
agyred switch you@gmail.com -t ide
agyred switch personal --target=all
```

Expired access tokens are refreshed automatically when a refresh token is available.

### Aliases

```bash
agyred alias work you@gmail.com
agyred switch work --target agy
agyred alias          # list
agyred unalias work
```

---

## Everyday usage

```bash
agyred list                       # accounts + quota summary (tags: cli / ide)
agyred info you@gmail.com         # per-model quotas
agyred status                     # active account snapshot
agyred refresh you@gmail.com
agyred refresh-all
agyred validate                   # refresh expired tokens only
agyred sync                       # local DB vs IDE vs CLI credentials
agyred doctor                     # diagnostics
agyred watch --interval 15        # live list
agyred remove you@gmail.com
agyred auto-switch --min 40 --model claude
```

---

## Data directory

Default: **`~/.antigravity-agent/`**

```plaintext
~/.antigravity-agent/
├── cloud_accounts.db    # SQLite (encrypted token/quota fields + settings)
├── .mk                  # AES-256 master key as hex (mode 0600)
└── aliases.json         # optional shortcuts
```

Created automatically on first use.

---

## How switching works

```plaintext
  agyred login / import-*
           │
           ▼
   ~/.antigravity-agent/
     cloud_accounts.db
           │
           │  agyred switch --target …
     ┌─────┴─────┐
     ▼           ▼
    agy         IDE
  keychain     vscdb
```

- **Credential store** — macOS Keychain (`gemini` / `antigravity`), Linux `secret-tool`, Windows Credential Manager
- **SQLite** — unified OAuth entry in Antigravity `state.vscdb` (`antigravityUnifiedStateSync.oauthToken`)

---

## Platform notes

| OS | Credential store |
|----|------------------|
| macOS | Keychain via `security` |
| Linux | `secret-tool` (libsecret) |
| Windows | Credential Manager (`gemini:antigravity`) |

Restarting IDE/desktop after `switch` is best-effort. Token injection still applies if the executable is not found.

---

## Security

- Tokens encrypted at rest with **AES-256-GCM** (`agyred_enc_v1:…`, also transparently decrypts legacy `agm_enc_v1:…`)
- Master key in `.mk` — keep `~/.antigravity-agent` private (`0700` / `0600`)
- Do not commit `.mk`, databases, or export files
- Uses the public Antigravity OAuth client (same as the official apps)

---

## Command reference

| Command | Description |
|---------|-------------|
| `init` | Create data dir, key, and empty DB |
| `login` / `add` | Browser OAuth |
| `import-cli` / `import-agy` | Import from agy credential store |
| `import-ide` | Import from IDE database |
| `list` / `ls` | List accounts |
| `info` / `status` | Details / snapshot |
| `switch` | Apply account to product surface(s) |
| `refresh` / `refresh-all` / `validate` | Tokens & quotas |
| `sync` / `doctor` | Status & diagnostics |
| `remove` / `rm` | Delete local account |
| `alias` / `unalias` | Shortcuts |
| `export` / `import-backup` | Backup |
| `auto-switch` | Best quota account |
| `watch` | Live monitoring |
| `help` | Help |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing database / master key | `agyred init` or `agyred login` |
| OAuth never completes | Free ports `8888`–`8892`; allow localhost |
| `import-cli` fails | Sign into `agy` once, or use `agyred login` |
| IDE switch finds no DB | Open Antigravity IDE once |
| Empty quotas | `agyred refresh <email>` |
| Expired tokens | `agyred validate` |

```bash
agyred doctor
```

---

## Development

```bash
go test ./...
go vet ./...
go build -o agyred .
```

```plaintext
.
├── main.go
├── go.mod                 # module github.com/ala2524/agyred
├── internal/
│   ├── api/               # OAuth, refresh, quota
│   ├── credstore/         # OS credential store
│   ├── crypto/            # master key + AES-GCM
│   ├── db/                # SQLite + IDE inject
│   ├── paths/
│   ├── process/
│   ├── proto/
│   ├── target/            # agy | ide | all
│   └── aliases/
└── README.md
```

---

## License

MIT License - See [LICENSE](./LICENSE) in this repository.

# SDP Migration Wizard v1.1

A CLI wizard that migrates configuration components between **ServiceDesk Plus On-Demand** instances.

---

## Supported Migrations

| Migration | Modules | Dependencies |
|-----------|---------|--------------|
| **UDF Migration** | Request, Problem, Change | — |
| **Template Migration** | Request | UDF Migration |

> **Note:** Template Migration depends on UDF Migration. The wizard will warn you if dependent migrations have not been run, and can auto-create missing UDFs on the target during template migration.

---

## Prerequisites

- Python 3.8 or later (pre-installed on macOS / most Linux distros)
- A **Zoho OAuth Client** (Client ID & Client Secret) with the required SDP scopes

---

## OAuth Setup — Getting Client ID, Client Secret & Grant Token

Before running the wizard you need a **Client ID**, **Client Secret**, and either a **Refresh Token** or a **Grant Token (Code)**. Follow these steps:

### 1. Register a Client

Open the Zoho API Console for your datacenter and create a **Server-based Application**:

| Datacenter | API Console Link |
|------------|-----------------|
| US / Global | [https://api-console.zoho.com](https://api-console.zoho.com) |
| EU | [https://api-console.zoho.eu](https://api-console.zoho.eu) |
| India | [https://api-console.zoho.in](https://api-console.zoho.in) |
| Australia | [https://api-console.zoho.com.au](https://api-console.zoho.com.au) |
| Japan | [https://api-console.zoho.jp](https://api-console.zoho.jp) |
| China | [https://api-console.zoho.com.cn](https://api-console.zoho.com.cn) |
| Canada | [https://api-console.zohocloud.ca](https://api-console.zohocloud.ca) |
| Saudi Arabia | [https://api-console.zoho.sa](https://api-console.zoho.sa) |

- Set **Redirect URI** to `https://www.zoho.com`
- Note down the **Client ID** and **Client Secret** shown after creation

### 2. Generate a Grant Token (Code)

In the same API Console page, go to the **Generate Code** tab (or use the self-client option) and enter the required scopes:

```
SDPOnDemand.setup.READ,SDPOnDemand.setup.CREATE,SDPOnDemand.setup.UPDATE
```

- Set scope duration and click **Create**
- Copy the generated **Code** — this is your Grant Token

> ⚠️ Grant Tokens expire in **~3 minutes**, so generate one right before running the wizard.

### 3. Authentication Methods

The wizard supports two authentication flows:

| Method | When to use |
|--------|-------------|
| **Refresh Token** | You already have a long-lived refresh token |
| **Grant Token (Code)** | You just generated a code from the API Console (recommended for first-time setup) |

When using a Grant Token, the wizard automatically exchanges it for a refresh + access token and revokes the generated refresh token at the end of the session.

---

## Usage

Everything is handled by a single launcher script — it creates an isolated virtual environment, installs dependencies, and runs the wizard automatically.

### CLI Mode (Terminal)

**macOS / Linux:**
```bash
./run.sh
```

**Windows:**
```bat
run.bat
```

### Web UI Mode (Browser)

**macOS / Linux:**
```bash
./run_ui.sh
```

This starts a local web server at `http://localhost:8080` with a step-by-step wizard UI. No manual `pip install` needed — the launcher handles everything.

### Interactive Prompts (CLI mode)

The CLI wizard will walk you through:

1. **Organization type** — same Zoho org (portal-to-portal) or different orgs
2. **Zoho Accounts URL** — based on your datacenter (US, EU, India, Australia, Japan, China, Canada, Saudi Arabia)
3. **OAuth credentials** — base URL, portal name, client ID, client secret, and refresh token or grant token
4. **Validation** — automatically tests the connection to both source and target instances
5. **Migration type** — UDF or Template migration
6. **Module & scope** — select the module and choose which items to migrate

---

## Logs

Every run creates timestamped log files under `logs/`:

| File | Contents |
|------|----------|
| `<timestamp>.log` | User-readable (INFO, WARN, ERROR) |
| `<timestamp>_debug.log` | Full detail (DEBUG + above) |

---

## Project Structure

```
run.sh / run.bat          — CLI launcher (start here)
run_ui.sh                 — Web UI launcher
migrate.py                — CLI entry point
app.py                    — Web UI entry point (NiceGUI)
requirements.txt          — CLI dependencies
requirements-ui.txt       — Web UI dependencies (extends CLI)

src/
  config/
    constants.py          — Zoho URLs, module config, supported migrations
    udf_config.py         — UDF type mappings and field config
    template_config.py    — Template field mappings
  services/               — Shared business logic (used by both CLI & Web UI)
    auth_service.py       — Token exchange, validation, client creation
    migration_service.py  — Migration type selection and handler dispatch
    udf_service.py        — UDF metadata fetching and comparison
    template_service.py   — Template fetching and pagination
  modules/                — CLI frontend layer
    auth.py               — CLI authentication prompts
    migration.py          — CLI migration selection prompts
    udf_migration.py      — UDF migration with CLI interaction
    template_migration.py — Template migration with CLI interaction
    logger.py             — Dual-file logger with console output + UI hook
  utils/
    http_client.py        — API client with automatic token refresh & revocation
    prompts.py            — Interactive CLI prompt helpers
logs/                     — Generated at runtime
```

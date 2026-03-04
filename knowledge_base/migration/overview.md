# SDP Migration Wizard — Architecture Overview

> **Purpose**: High-level reference for any AI tool or developer to understand, navigate, and extend this project.  
> **Role**: This is the **face page** — start here, then follow links to module-specific docs.  
> **Last updated**: 2026-02-27  
> **Keep this file in sync with every structural change.**

---

## Quick Navigation — Module Deep Dives

| Module | File | Status |
|---|---|---|
| Authentication | [`auth.md`](auth.md) | Implemented |
| UDF Migration | [`udf_migration.md`](udf_migration.md) | Implemented |
| Template Migration | [`template_migration.md`](template_migration.md) | Implemented |

> **AI agents**: For any task involving a specific migration type, read the corresponding module file above. This face page covers shared architecture only.

---

## 1. Project Overview

A **Python migration wizard** (CLI + Web UI) that migrates configuration components (UDFs, Templates, etc.) between ServiceDesk Plus On-Demand instances.

### Goals
- Click-and-go experience (launcher scripts handle setup)
- Runs on any machine with Python 3.8+
- **Dual interface**: CLI (terminal prompts) and Web GUI (NiceGUI)
- **Config-driven**: adding new migration types requires only config changes — zero CLI/GUI code changes
- Modular three-layer architecture: CLI, GUI, and Core are fully independent
- Proper logging for every run

### Runtime
- **Language**: Python 3
- **CLI Dependencies**: `requests`, `questionary`, `colorama` (see `requirements.txt`)
- **GUI Dependencies**: `nicegui` (see `requirements-ui.txt`)
- **CLI Entry point**: `python migrate.py` (or use `run.sh` / `run.bat`)
- **GUI Entry point**: `python app.py` (or use `run_ui.sh`)

---

## 2. Three-Layer Architecture

The codebase is split into three independent layers. CLI and GUI are thin wrappers over shared Core logic.

| Layer | Files | Purpose |
|---|---|---|
| **CLI** | `migrate.py`, `run.sh`, `src/modules/auth.py`, `src/modules/migration.py`, `src/utils/prompts.py` | Terminal prompts via `questionary` |
| **GUI** | `app.py`, `run_ui.sh`, `requirements-ui.txt` | Web UI via `NiceGUI` |
| **Core** | `src/services/*`, `src/modules/udf_migration.py`, `src/modules/template_migration.py`, `src/utils/http_client.py`, `src/modules/logger.py`, `src/config/*` | Business logic, config, HTTP |

> **Key rule**: Handlers (`udf_migration.py`, `template_migration.py`) have **zero CLI/GUI imports**. They accept data as required parameters and execute pure migration logic.

---

## 3. Project Structure

```
run.sh / run.bat              — CLI launcher (auto venv + deps + run)
run_ui.sh                     — GUI launcher
migrate.py                    — CLI entry point
app.py                        — GUI entry point (NiceGUI web app)
requirements.txt              — CLI Python dependencies
requirements-ui.txt           — GUI Python dependencies (nicegui)
src/
  __init__.py
  config/
    __init__.py
    constants.py              — Zoho URLs, MODULE_CONFIG, SUPPORTED_MIGRATIONS (registry config)
    udf_config.py             — UDF-specific: field type prefixes, skip keys, constraints
    template_config.py        — Template-specific: allowed keys, skip keys, page size
  services/                   — Pure business logic (used by both CLI and GUI)
    __init__.py
    auth_service.py           — Token management, client creation, validation
    migration_service.py      — Handler registry, item loader registry, step helpers
    udf_service.py            — UDF context fetching, metadata retrieval
    template_service.py       — Template fetching, module config, ID resolution
  modules/
    __init__.py
    logger.py                 — Dual-file logger with console output + UI callback hook
    auth.py                   — CLI-only: interactive auth prompts
    migration.py              — CLI-only: migration selection + generic step renderer
    udf_migration.py          — Core: UDF migration logic (zero CLI imports)
    template_migration.py     — Core: Template migration logic (zero CLI imports)
  utils/
    __init__.py
    http_client.py            — SdpClient with auto token refresh
    prompts.py                — CLI-only: questionary prompt wrappers
logs/                         — Created at runtime (gitignored)
knowledge_base/
  migration/
    overview.md                — THIS FILE (high-level overview)
    auth.md                   — Auth module deep dive
    udf_migration.md          — UDF migration deep dive
    template_migration.md     — Template migration deep dive
```

---

## 4. Registry Config System

All migration types are declared in `constants.py` → `SUPPORTED_MIGRATIONS`. Each type has a `steps` list that drives **both** CLI and GUI generically — no `if/elif` per migration type anywhere.

### Step Types

| Type | Key Fields | CLI Widget | GUI Widget |
|---|---|---|---|
| `item_selection` | `modes`, `item_loader`, `item_key`, `item_label` | `select()` → `checkbox()` | `ui.select()` → Load Items → checkboxes |
| `toggle` | `label`, `default` | `confirm()` | `ui.switch()` |
| `text_input` | `label` | `text()` | `ui.input()` |

### Conditional Steps

Steps can have a `condition` dict to control visibility:

```python
"condition": {"mode_in": ["all", "selected"]}   # show only for these modes
"condition": {"module_in": ["service_request"]}  # show only for these modules
```

### Current Config

```python
SUPPORTED_MIGRATIONS = {
    "udf": {
        "label": "UDF Migration",
        "supported_modules": ["request", "problem", "change"],
        "dependencies": [],
        "steps": [
            {
                "key": "selected_udfs",
                "type": "item_selection",
                "modes": [
                    {"value": "all", "label": "All UDFs — migrate everything"},
                    {"value": "selected", "label": "Selected UDFs — choose from list"},
                ],
                "item_loader": "load_udfs",
                "item_key": "key",
                "item_label": "{display_name}  ({field_type})",
            },
        ],
    },
    "template": {
        "label": "Template Migration",
        "supported_modules": ["request"],
        "dependencies": ["udf"],
        "steps": [
            {
                "key": "selected_templates",
                "type": "item_selection",
                "modes": [
                    {"value": "all", "label": "All templates — migrate everything"},
                    {"value": "selected", "label": "Selected — choose from list"},
                    {"value": "source_ids", "label": "Source IDs — provide template IDs"},
                ],
                "item_loader": "load_templates",
                "item_key": "id",
                "item_label": "{name}",
            },
            {
                "key": "include_inactive",
                "type": "toggle",
                "label": "Include inactive templates",
                "default": False,
                "condition": {"mode_in": ["all", "selected"]},
            },
        ],
    },
}
```

### Item Loaders

`ITEM_LOADERS` in `migration_service.py` maps loader keys to fetch functions:

| Key | Function | Returns |
|---|---|---|
| `load_udfs` | `_load_udf_items()` → `get_udf_context()` | UDF dicts with `key`, `display_name`, `field_type` |
| `load_templates` | `_load_template_items()` → `fetch_all_templates()` | Template dicts with `id`, `name` |

---

## 5. Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python | Better for scripting/automation; simpler deps |
| HTTP client | `requests` | Synchronous, simple, widely available |
| CLI prompts | `questionary` | Modern, built on prompt_toolkit, supports list/confirm/text/password |
| Web UI | `NiceGUI` | Python-native; no separate frontend; auto-refresh; built on Quasar |
| Console colors | `colorama` | Cross-platform ANSI color support |
| Logging library | Custom (`logger.py`) | Lightweight dual-file logger with UI callback hook for GUI |
| Setup | `run.sh` / `run.bat` / `run_ui.sh` | Auto-creates venv, installs deps — user never runs `pip` manually |
| Migration per run | One type at a time | Keeps session clean; shows dependency warnings |
| Config-driven steps | Registry pattern | New migration types = config only, zero CLI/GUI code changes |

---

## 6. API Conventions

### URL Format
```
{base_url}/app/{portal}/api/v3/{endpoint}
```
- `base_url`: Service domain or custom domain (e.g., `https://sdpondemand.manageengine.com`)
- `portal`: Portal name (e.g., `my_portal`)

### Common Headers
```
Accept: application/vnd.manageengine.sdp.v3+json
Authorization: Zoho-oauthtoken <ACCESS_TOKEN>
Content-Type: application/x-www-form-urlencoded
```

### POST Body Convention
POST requests send data as form-encoded with key `input_data` containing a JSON string:
```
input_data={"udf_field": { ... }}
```

### Success Validation
`response_status[0].status_code == 2000` indicates success.

---

## 7. Shared Modules

### 7.1 — Services Layer (`src/services/`)

Pure business logic used by both CLI and GUI. **Zero UI dependencies.**

| Service | Responsibility |
|---|---|
| `auth_service.py` | Token stores, client creation, token exchange, validation |
| `migration_service.py` | Handler registry, item loader registry, step config helpers |
| `udf_service.py` | UDF metadata fetching, context building (source vs target comparison) |
| `template_service.py` | Template module config, template fetching, ID resolution |

### 7.2 — Logging (`src/modules/logger.py`)

- **Singleton**: `logger = Logger()` at module level; import and use everywhere
- **Init**: `logger.init()` creates `logs/` dir and two files per session:
  - `{timestamp}_debug.log` — all levels (DEBUG, INFO, WARN, ERROR)
  - `{timestamp}.log` — user-readable (INFO, WARN, ERROR)
- **Console**: INFO/WARN/ERROR print to console with colors (green=success, yellow=warn, red=error)
- **UI callback hook**: `logger.set_ui_callback(fn)` — GUI calls this to pipe logs to the web UI
- **Methods**: `logger.debug()`, `logger.info()`, `logger.success()`, `logger.warn()`, `logger.error()`

### 7.3 — HTTP Client (`src/utils/http_client.py`)

- **SdpClient** class: wraps `requests` with auto token refresh
- On HTTP 401 → calls `TokenStore.generate_token()` → retries the request
- Shared token store: both source/target clients reference the same TokenStore object (by reference) when `same_instance = true`

---

## 8. Entry Point Flows

### CLI (`migrate.py`)

```
1. logger.init()
2. Print welcome banner
3. run_auth() → (source_client, target_client)        [prompts via questionary]
4. If auth fails → exit
5. run_migration_selection() → (migration_type, module) [prompts via questionary]
6. collect_migration_items() → selection kwargs          [generic step loop]
7. run_migration(type, src, tgt, module, **kwargs)       [dispatches to handler]
8. revoke_tokens() + logger.close()
```

### GUI (`app.py`)

```
1. 5-step NiceGUI wizard:
   Step 1: Same org? + Zoho Accounts URL
   Step 2: Source credentials (NiceGUI forms → auth_service)
   Step 3: Target credentials + validate both
   Step 4: Migration type + module + config steps (generic from registry)
   Step 5: Execute migration + live log output
2. rebuild_steps() dynamically builds UI widgets from config
3. execute_migration() builds kwargs by reading step widget values (generic loop)
4. run_migration(type, src, tgt, module, **kwargs)
```

---

## 9. Key Behavioural Decisions

| Topic | Decision | Why |
|---|---|---|
| One migration per run | **Yes** | Keeps session clean; dependency warnings shown |
| Dependency warning | **Warning only** | Doesn't block; user may have migrated deps in a previous run |
| Console vs debug log | **Console: crisp. Debug: verbose.** | Keep user log readable |
| Abort on individual failure | **No** — continue and log | Per-item pass/fail + summary at end |

---

## 10. Extending the Project

### Adding a new migration type
1. Add entry to `SUPPORTED_MIGRATIONS` in `constants.py` with `steps` list
2. Create `src/modules/{type}_migration.py` — **pure logic, zero CLI/GUI imports**, required selection parameter
3. Register handler in `migration_service.py` → `MIGRATION_HANDLERS`
4. Add item loader in `migration_service.py` → `ITEM_LOADERS` (if it needs item selection)
5. Add config file if needed: `src/config/{type}_config.py`
6. Create `knowledge_base/migration/{type}_migration.md`
7. **Update this file** (Quick Navigation table + project structure)

> **No changes to CLI (`migration.py`) or GUI (`app.py`) required.** Both iterate config steps generically.

### Adding a new module to an existing migration
1. Add the module name to the `supported_modules` list in `SUPPORTED_MIGRATIONS`
2. Add entry to `MODULE_CONFIG` in `constants.py`
3. Test the metainfo endpoint for the new module
4. **Update the corresponding module doc** in `migration/`

### Adding sub-components to a migration
Add `toggle` steps to the migration's `steps` list in `SUPPORTED_MIGRATIONS`:
```python
{"key": "template_tasks", "type": "toggle", "label": "Migrate Template Tasks", "default": True},
{"key": "resource_config", "type": "toggle", "label": "Migrate Resource Config", "default": True,
 "condition": {"module_in": ["service_request"]}},
```
CLI auto-renders `confirm()` prompts. GUI auto-renders `ui.switch()` widgets. Handler receives them as kwargs.

### Adding a new UDF field type
1. Add entry to `UDF_FIELD_TYPE_PREFIX` in `udf_config.py`
2. **Update** [`migration/udf_migration.md`](migration/udf_migration.md) §4 Field Type Config table

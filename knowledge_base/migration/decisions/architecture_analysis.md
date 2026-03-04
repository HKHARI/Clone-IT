# SDP Migration Wizard — Architecture Guide

## Three-Layer Architecture

The codebase is split into three independent layers. CLI and GUI are thin wrappers — all business logic lives in Core.

```mermaid
graph TD
    subgraph "CLI Layer"
        CLI_ENTRY["migrate.py"]
        CLI_AUTH["src/modules/auth.py"]
        CLI_MIG["src/modules/migration.py"]
        CLI_PROMPTS["src/utils/prompts.py"]
    end

    subgraph "GUI Layer"
        GUI_ENTRY["app.py"]
    end

    subgraph "Core Layer"
        CONFIG["src/config/constants.py<br/>Registry config + steps"]
        SVC_MIG["src/services/migration_service.py<br/>Item loaders + step helpers"]
        SVC_AUTH["src/services/auth_service.py"]
        SVC_UDF["src/services/udf_service.py"]
        SVC_TPL["src/services/template_service.py"]
        UDF_H["src/modules/udf_migration.py<br/>Pure migration logic"]
        TPL_H["src/modules/template_migration.py<br/>Pure migration logic"]
        HTTP["src/utils/http_client.py"]
        LOGGER["src/modules/logger.py"]
    end

    CLI_ENTRY --> CLI_AUTH --> SVC_AUTH
    CLI_ENTRY --> CLI_MIG -->|"generic step loop"| SVC_MIG
    CLI_AUTH --> CLI_PROMPTS
    CLI_MIG --> CLI_PROMPTS

    GUI_ENTRY -->|"NiceGUI forms"| SVC_AUTH
    GUI_ENTRY -->|"generic step loop"| SVC_MIG

    CONFIG --> SVC_MIG
    SVC_MIG --> UDF_H --> SVC_UDF --> HTTP
    SVC_MIG --> TPL_H --> SVC_TPL --> HTTP

    style CLI_ENTRY fill:#4ecdc4,color:#fff
    style CLI_AUTH fill:#4ecdc4,color:#fff
    style CLI_MIG fill:#4ecdc4,color:#fff
    style CLI_PROMPTS fill:#4ecdc4,color:#fff
    style GUI_ENTRY fill:#f39c12,color:#fff
    style UDF_H fill:#45b7d1,color:#fff
    style TPL_H fill:#45b7d1,color:#fff
    style CONFIG fill:#9b59b6,color:#fff
    style SVC_MIG fill:#45b7d1,color:#fff
```

---

## File Ownership

| Layer | Files | Purpose |
|-------|-------|---------|
| **CLI** | [migrate.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/migrate.py), [run.sh](file:///Users/harish-7052/Work/Workspace/Presales_scripts/run.sh), [src/modules/auth.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/auth.py), [src/modules/migration.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/migration.py), [src/utils/prompts.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/prompts.py) | Terminal prompts via `questionary` |
| **GUI** | [app.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/app.py), [run_ui.sh](file:///Users/harish-7052/Work/Workspace/Presales_scripts/run_ui.sh), [requirements-ui.txt](file:///Users/harish-7052/Work/Workspace/Presales_scripts/requirements-ui.txt) | Web UI via `NiceGUI` |
| **Core** | `src/services/*`, [src/modules/udf_migration.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/udf_migration.py), [src/modules/template_migration.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/template_migration.py), [src/utils/http_client.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/http_client.py), [src/modules/logger.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/logger.py), `src/config/*` | Business logic, config, HTTP |

> [!IMPORTANT]
> Handlers ([udf_migration.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/udf_migration.py), [template_migration.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/template_migration.py)) have **zero CLI/GUI imports**. They accept data and execute — no prompts, no UI widgets.

---

## Registry Config System

All migration types are declared in [constants.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/config/constants.py) → `SUPPORTED_MIGRATIONS`. Each type has a [steps](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py#113-117) list that drives **both** CLI and GUI generically.

### Step Types

| Type | Key Fields | CLI Widget | GUI Widget |
|------|-----------|------------|------------|
| [item_selection](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/migration.py#101-151) | `modes`, `item_loader`, `item_key`, `item_label` | [select()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/prompts.py#13-24) → [checkbox()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/prompts.py#43-57) | `ui.select()` → Load Items → checkboxes |
| [toggle](file:///Users/harish-7052/Work/Workspace/Presales_scripts/app.py#754-762) | `label`, [default](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/template_migration.py#288-307) | [confirm()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/prompts.py#6-11) | `ui.switch()` |
| `text_input` | `label` | [text()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/utils/prompts.py#26-34) | `ui.input()` |

### Conditional Steps

Steps can have a [condition](file:///Users/harish-7052/Work/Workspace/Presales_scripts/app.py#462-469) dict to control visibility:

```python
"condition": {"mode_in": ["all", "selected"]}   # show only for these modes
"condition": {"module_in": ["service_request"]}  # show only for these modules
```

Conditions are evaluated by [should_show_step()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py#119-140) in [migration_service.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py).

### Item Loaders

`ITEM_LOADERS` in [migration_service.py](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py) maps loader keys to fetch functions:

| Key | Function | Returns |
|-----|----------|---------|
| `load_udfs` | [_load_udf_items()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py#33-39) → [get_udf_context()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/udf_service.py#11-67) | UDF dicts with [key](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/template_migration.py#321-359), `display_name`, `field_type` |
| `load_templates` | [_load_template_items()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/migration_service.py#41-48) → [fetch_all_templates()](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/services/template_service.py#22-38) | Template dicts with [id](file:///Users/harish-7052/Work/Workspace/Presales_scripts/src/modules/auth.py#18-25), `name` |

### Current Config

```python
SUPPORTED_MIGRATIONS = {
    "udf": {
        "steps": [
            {type: "item_selection", modes: ["all", "selected"], item_loader: "load_udfs"},
        ],
    },
    "template": {
        "steps": [
            {type: "item_selection", modes: ["all", "selected", "source_ids"], item_loader: "load_templates"},
            {type: "toggle", key: "include_inactive", condition: {mode_in: ["all", "selected"]}},
        ],
    },
}
```

---

## Control Flow — UDF Migration

```mermaid
flowchart TD
    A["User starts UDF migration"]

    subgraph "CLI Path"
        C1["migrate.py → auth.py<br/>collect credentials via prompts"]
        C2["migration.py<br/>run_migration_selection() → prompts"]
        C3["migration.py<br/>collect_migration_items() → generic step loop"]
        C4["Mode: All → passes all keys<br/>Mode: Selected → checkbox prompt"]
        C5["migration_service.run_migration()<br/>kwargs: selected_udfs = list"]
        C6["udf_migration.run_udf_migration()<br/>selected_udfs is required"]
    end

    subgraph "GUI Path"
        G1["app.py Steps 1-3<br/>NiceGUI forms → auth_service"]
        G2["app.py Step 4<br/>rebuild_steps() → mode dropdown"]
        G3["Mode: All → svc_load_items()<br/>Mode: Selected → checkboxes"]
        G4["migration_service.run_migration()<br/>kwargs: selected_udfs = list"]
        G5["udf_migration.run_udf_migration()<br/>selected_udfs is required"]
    end

    A --> C1 --> C2 --> C3 --> C4 --> C5 --> C6
    A --> G1 --> G2 --> G3 --> G4 --> G5
```

## Control Flow — Template Migration

```mermaid
flowchart TD
    A["User starts Template migration"]

    subgraph "CLI Path"
        C1["migrate.py → auth + selection"]
        C2["migration.py<br/>collect_migration_items() → generic step loop"]
        C3A["Mode: All → load all templates"]
        C3B["Mode: Selected → checkbox prompt"]
        C3C["Mode: Source IDs → text prompt"]
        C4["toggle: include_inactive?<br/>(only for all/selected modes)"]
        C5["migration_service.run_migration()<br/>kwargs: selected_templates = list"]
        C6["template_migration.run_template_migration()<br/>selected_templates is required"]
    end

    subgraph "GUI Path"
        G1["app.py Steps 1-3<br/>NiceGUI forms"]
        G2["app.py Step 4<br/>rebuild_steps() → mode dropdown + toggle"]
        G3A["Mode: All → svc_load_items()"]
        G3B["Mode: Selected → Load Items → checkboxes"]
        G3C["Mode: Source IDs → resolve_by_ids()"]
        G4["migration_service.run_migration()<br/>kwargs: selected_templates = list"]
        G5["template_migration.run_template_migration()<br/>selected_templates is required"]
    end

    A --> C1 --> C2
    C2 --> C3A --> C4 --> C5 --> C6
    C2 --> C3B --> C4
    C2 --> C3C --> C5

    A --> G1 --> G2
    G2 --> G3A --> G4 --> G5
    G2 --> G3B --> G4
    G2 --> G3C --> G4
```

---

## How to Add a New Migration Type

1. **Add handler** in `src/modules/` (e.g. `workflow_migration.py`) — pure logic, accepts selections as required params
2. **Register handler** in `migration_service.py` → `MIGRATION_HANDLERS`
3. **Add item loader** in `migration_service.py` → `ITEM_LOADERS` (if it needs item selection)
4. **Add config** in `constants.py` → `SUPPORTED_MIGRATIONS` with `steps` list

**Zero changes to CLI or GUI code.** Both iterate steps generically.

### Example: Adding sub-components to Template

To add toggles like "Migrate Template Tasks", "Migrate Checklist", "Resource Config (service templates only)":

```python
"template": {
    "steps": [
        {type: "item_selection", ...},        # existing
        {type: "toggle", key: "include_inactive", ...},  # existing
        # NEW — just add these:
        {type: "toggle", key: "template_tasks", label: "Migrate Template Tasks", default: True},
        {type: "toggle", key: "checklist", label: "Migrate Checklist", default: True},
        {
            type: "toggle", key: "resource_config",
            label: "Migrate Resource Configuration", default: True,
            condition: {"module_in": ["service_request"]},
        },
    ],
}
```

CLI auto-renders `confirm()` prompts. GUI auto-renders `ui.switch()` widgets. Handler receives them as kwargs.

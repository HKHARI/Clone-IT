# Template Migration Module — `src/modules/template_migration.py`

> **Scope**: Template migration lifecycle — fetch, UDF dependency resolution, payload trimming, create  
> **Parent**: [`overview.md`](overview.md)  
> **Handler**: `src/modules/template_migration.py` (pure logic — zero CLI/GUI imports)  
> **Service**: `src/services/template_service.py` (fetching, config, ID resolution)  
> **Config**: `src/config/template_config.py`  
> **Status**: Implemented  
> **Last updated**: 2026-02-27

---

## 1. Dependencies

| Dependency | Reason |
|---|---|
| UDF Migration | Templates may reference UDF fields. If source template contains UDFs not present in target, they must be created first. |

> A dependency warning is shown before template migration runs (handled by `src/modules/migration.py`).

---

## 2. Supported Modules

| Module | Entity Singular | Entity Plural | Template Entity Singular | Template Entity Plural | Status |
|---|---|---|---|---|---|
| Request | `request` | `requests` | `request_template` | `request_templates` | Implementing |
| Service Request | — | — | — | — | Future |
| Problem | — | — | — | — | Future |
| Change | — | — | — | — | Future |

> **Important**: Request and Service Request share the same `request_templates` API endpoint.  
> They are differentiated by `is_service_template`: `false` for Request, `true` for Service Request.  
> Each module's `template_list_criteria` in `MODULE_CONFIG` (`constants.py`) controls the filter applied when listing templates.

---

## 3. Migration Flow

### Step 1 — Template Selection (handled by calling layer)

> **Note**: Selection is now handled by the CLI (`migration.py`) or GUI (`app.py`) via the registry config in `SUPPORTED_MIGRATIONS`. The handler receives `selected_templates` as a **required** parameter. See [`overview.md`](overview.md) §4 Registry Config.

Three selection modes defined in config: **All**, **Selected**, or **Source IDs**.

- **All**:
  - Fetch all templates from source (via `template_service.fetch_all_templates()`)
  - `search_criteria` from `template_list_criteria` filters by module (e.g. `is_service_template = false`)
  - Toggle: include inactive templates? (config step `include_inactive`)
  - Default template (`is_default: true`) is **included**
  - Migrate all fetched templates

- **Selected**:
  - Fetch all templates from source (same as All)
  - Toggle: include inactive templates?
  - CLI: paginated **15 per page** with Next/Back navigation
  - GUI: scrollable checkboxes with Select All
  - Migrate only selected templates

- **Source IDs**:
  - User provides **comma-separated template IDs**
  - **Skip** the "include inactive?" toggle
  - Resolved via `template_service.resolve_by_ids()`
  - Migrate all provided IDs

### Step 2 — Build UDF Field Map

Create a mapping between source and target UDF fields using `display_name` as the key.

- Fetch UDF metadata from both source and target (`GET /{entity_plural}/_metainfo`)
- Build map: `source_field_key → target_field_key` (matched by `display_name`)

### Step 3 — UDF Dependency Resolution (per template)

While processing each template's layout fields:
- Identify UDF field references (`udf_fields.<key>`)
- If a UDF key is **not in the map** (missing on target):
  - Fetch full UDF details from source (`GET /udf_fields/{id}`)
  - Create the UDF on target (reuse UDF migration payload-building + POST logic)
  - Update the source→target UDF map with the new mapping
  - Log the auto-created UDF
- Only creates UDFs that the template actually uses — not a full UDF migration

### Step 4 — Fetch Template Data

Two API calls per template:

1. **Template root data** (metadata):
   ```
   GET {base}/app/{portal}/api/v3/{template_entity_plural}/{id}/_get_template_with_layout
   ```
   Returns: name, comments, show_to_requester, service_category, task_configuration, reference_templates, etc.

2. **Layout structure** (form fields):
   ```
   GET {base}/app/{portal}/api/v3/{template_entity_plural}/{id}/layouts
   ```
   Returns: layouts → sections → fields (with default_value, scopings, etc.)

### Step 5 — Trim and Transform Payload

The raw GET responses **cannot** be used directly for POST. Each level has specific trim rules.
All trim logic is kept in **separate modular functions** so it can be updated independently.

#### 5a — Template Root

- Copy **only** keys in `ALLOWED_TEMPLATE_KEYS`:
  `name`, `comments`, `reference_templates`, `show_to_requester`, `task_configuration`, `is_service_template`, `service_category`, `is_cost_enabled`, `image`, `cost_details`
- `service_category`: if not null, reduce to `{"name": <name>}`
- `reference_templates`, `task_configuration`: copy **as-is** (may contain IDs; update handling in future if failures occur)

#### 5b — Layout

- Strip `id` and `GLOBAL_SKIP_KEYS`
- `help_text`: if present, iterate each entry and remove `GLOBAL_SKIP_KEYS` from it
- `sections`: do **not** copy directly — rebuild via Section trim (5c)

#### 5c — Section

- Copy all section keys except `id`, `fields`, `GLOBAL_SKIP_KEYS`, `SKIP_SECTION_KEYS`
- `fields`: do **not** copy directly — rebuild via Field trim (5d)

#### 5d — Field

- Strip `template_id` (`SKIP_FIELD_KEYS`)
- **UDF name mapping**: if field `name` starts with `udf_fields.`, split on `.`, replace the UDF key portion with the target key from the UDF map. If UDF key not found in map → trigger UDF auto-creation (Step 3).
- **default_value** — Deluge-style handling:
  - If entry is `null` → keep `null`
  - If `entry["value"]` is `null` → `{"value": null}`
  - If `entry["value"]` is string/number → `{"value": val}`
  - If `entry["value"]` is object → extract first found key from `["email_id", "internal_name", "name", "value"]` → `{"value": {key: extracted}}`
  - Fallback (extraction fails) → `{"value": original_object}`
- **scopings**: copy each scoping entry, removing `GLOBAL_SKIP_KEYS`
- **remaining field keys**: copy unless already set, in `GLOBAL_SKIP_KEYS`, or in `SKIP_FIELD_KEYS`

### Step 6 — Create Template on Target

```
POST {base}/app/{portal}/api/v3/{template_entity_plural}
Body: input_data = {template_entity_singular: {trimmed_root + "layouts": [trimmed_layouts]}}
```

- Success: log `[OK] Template Name`
- Failure: log `[FAIL] Template Name` to console; log payload + URL + response + error to **debug log only**
- **Continue on failure** — never abort

### Step 7 — Summary

Console output:
```
==================================================
Template Migration Complete: 8 / 12 migrated successfully

Failed (2):
  - Template Name A
  - Template Name B

UDFs auto-created during migration (3):
  - My Custom Field  (Single Line) → txt_my_custom_field
  - Priority Extra   (Pick List) → txt_priority_extra
  - Risk Score        (Numeric Field) → num_risk_score
==================================================
```

---

## 4. Configuration

### Module Config (`src/config/constants.py` → `MODULE_CONFIG`)

Template-specific keys are added to the shared `MODULE_CONFIG` alongside entity names. No separate module config.

```python
"request": {
    "entity_singular": "request",
    "entity_plural": "requests",
    "udf_field_holder": "udf_fields",
    "template_entity_singular": "request_template",
    "template_entity_plural": "request_templates",
    "template_list_criteria": [
        {"field": "is_service_template", "condition": "eq", "value": False, "logical_operator": "and"},
    ],
},
```

> `template_list_criteria` is passed as `search_criteria` in `list_info` when fetching templates.  
> This is how Request (`is_service_template = false`) is separated from Service Request (`is_service_template = true`) on the same `request_templates` endpoint.

### Skip / Allow Keys (`src/config/template_config.py`)

| Constant | Values | Purpose |
|---|---|---|
| `ALLOWED_TEMPLATE_KEYS` | `name`, `comments`, `reference_templates`, `show_to_requester`, `task_configuration`, `is_service_template`, `service_category`, `is_cost_enabled`, `image`, `cost_details` | Only these keys copied from template root |
| `SKIP_FIELD_KEYS` | `template_id` | Field-level keys to skip |
| `DEFAULT_VALUE_EXTRACT_KEYS` | `email_id`, `internal_name`, `name`, `value` | Keys to try when extracting object default values |
| `PAGE_SIZE` | `15` | Templates per page in selection UI |
| `UNSUPPORTED_FIELD_REASONS` | `{"assets": "Asset Disabled"}` | Fields rejected when a target feature is disabled — key = field name, value = reason shown in summary |

> `GLOBAL_SKIP_KEYS` (`id`, `attachment`, `attachments`) is reused from `src/config/udf_config.py`.

---

## 5. Logging Rules

| Destination | What gets logged |
|---|---|
| Console + `.log` file | Success/fail per template + final summary |
| `_debug.log` file | Full payloads, API responses, UDF auto-creation details, unsupported field detection |

---

## 6. Unsupported Field Detection

Some template fields (e.g. `assets`) are rejected by the SDP API when the corresponding feature is disabled on the target instance. The migration handles this automatically:

1. **First template with the field** → POST fails → error response is parsed → field detected → marked as `[FAIL] Template Name — [Asset Disabled]` → field added to session-level `skip_fields` set
2. **Subsequent templates with the same field** → pre-check detects the field in layouts → POST is **skipped entirely** → marked as `[FAIL] Template Name — [Asset Disabled]`
3. **If detection fails** → normal failure (no reason tag), remaining templates continue normally

### Error Detection

The API error response has this structure:
```json
{"response_status": {"messages": [{"message": {"response_status": [{"messages": [{"message": "[assets] field/s cannot be added to the template"}]}]}}]}}
```

The detector traverses the nested JSON and extracts field names from `[field_name]` via regex. Only fields present in `UNSUPPORTED_FIELD_REASONS` are recognized.

### Extending

To handle a new unsupported field, add one line to `UNSUPPORTED_FIELD_REASONS` in `template_config.py`:
```python
UNSUPPORTED_FIELD_REASONS = {
    "assets": "Asset Disabled",
    "new_field": "Feature X Disabled",  # ← just add this
}
```
No code changes required.

---

## 7. Summary Output

```
==================================================
Template Migration Complete: 5 / 8 migrated successfully

Failed (3):
  - Sample template  [Asset Disabled]
  - Another template  [Asset Disabled]
  - Broken template

UDFs auto-created during migration (1):
  - My Custom Field  (Single Line) → txt_my_custom_field
==================================================
```

---

## 8. API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `{base}/app/{portal}/api/v3/{template_entity_plural}` | GET | List all templates (with `list_info` for pagination + inactive filter) |
| `{base}/app/{portal}/api/v3/{template_entity_plural}/{id}/_get_template_with_layout` | GET | Get template root data (metadata) |
| `{base}/app/{portal}/api/v3/{template_entity_plural}/{id}/layouts` | GET | Get template layouts (sections, fields, defaults, scopings) |
| `{base}/app/{portal}/api/v3/{template_entity_plural}` | POST | Create template on target |

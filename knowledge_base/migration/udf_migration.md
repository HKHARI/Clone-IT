# UDF Migration Module — `src/modules/udf_migration.py`

> **Scope**: Full UDF migration lifecycle — fetch, compare, transform, create, summarize  
> **Parent**: [`overview.md`](overview.md)  
> **Handler**: `src/modules/udf_migration.py` (pure logic — zero CLI/GUI imports)  
> **Service**: `src/services/udf_service.py` (context fetching, metadata retrieval)  
> **Config**: `src/config/udf_config.py`  
> **Last updated**: 2026-02-27

---

## 1. Module-Specific Configuration

Each module (request, problem, change) may have different API naming. Stored in `MODULE_CONFIG`:

```python
MODULE_CONFIG = {
    "request": {
        "entity_singular": "request",
        "entity_plural": "requests",
        "udf_field_holder": "udf_fields",
    },
    "problem": {
        "entity_singular": "problem",
        "entity_plural": "problems",
        "udf_field_holder": "udf_fields",
    },
    "change": {
        "entity_singular": "change",
        "entity_plural": "changes",
        "udf_field_holder": "udf_fields",
    },
}
```

> `udf_field_holder` is currently `"udf_fields"` for all modules. If a module differs in the future, update only this config.

---

## 2. Migration Flow (7 Steps)

### Step 1 — Fetch UDF Metadata

```
Source: GET /{entity_plural}/_metainfo
Target: GET /{entity_plural}/_metainfo
```

Extract: `response["metainfo"]["fields"][udf_field_holder]["fields"]`

- Source gives: `{udf_key: {id, display_name, field_type}, ...}`
- Target gives: same structure
- Build target map: `display_name → field_key`

### Step 2 — Compare

For each source UDF:
- Target has a UDF with the same `display_name` → **skip** (already exists), record key mapping
- Not found → add to **"to migrate" list**

Log: `"Found X UDFs on source, Y on target, Z need migration"`

### Step 3 — User Selection (handled by calling layer)

> **Note**: Selection is now handled by the CLI (`migration.py`) or GUI (`app.py`) via the registry config in `SUPPORTED_MIGRATIONS`. The handler receives `selected_udfs` as a **required** parameter. See [`overview.md`](overview.md) §4 Registry Config.

- Two modes defined in config: **All** or **Selected**
- CLI: `confirm()` → all, or `checkbox()` with display_name + field_type
- GUI: dropdown mode selector → Load Items → scrollable checkboxes

### Step 4 — Fetch Full UDF Details (per UDF)

```
GET /udf_fields/{udf_id}
```

Response: `{"udf_field": { full details }}`

### Step 5 — Build Creation Payload

This is the most complex step. Broken into sub-steps:

#### 5a — Field Key Generation

**Only for `request` module.** For `problem`/`change`, `field_key` is omitted from the payload entirely — the API assigns it. Those modules use `module: {internal_name: "problem"/"change"}` instead.

For `request` module, only when source `field_key` starts with `udf_` (legacy keys):

1. Look up config from `UDF_FIELD_TYPE_CONFIG` based on `field_type` → get `prefix` and `max_length`
2. If field type not found → mark UDF as **unsupported**, skip it (listed in summary)
3. Lowercase the UDF `name`
4. Replace all non-alphanumeric characters with `_`
5. Collapse consecutive underscores into one
6. Strip leading/trailing `_` from name portion
7. Final key = `{prefix}{sanitized_name}`
8. Truncate to `max_length`, strip any trailing `_` caused by the cut

For keys that do NOT start with `udf_` → keep the original `field_key` as-is.

#### 5b — Constraints

```python
ALLOWED_CONSTRAINT_KEYS = {"constraint_name", "constraint_value"}

SKIP_CONSTRAINT_NAMES = {
    "criteria", "regex", "digits", "unique_collection",
    "picklist", "lower_case", "editable", "collection"
}
```

Processing:
1. Iterate source constraints
2. Skip if `constraint_name` is in `SKIP_CONSTRAINT_NAMES` or `GLOBAL_SKIP_KEYS`
3. Copy only `constraint_name` and `constraint_value`
4. Hold `min_length` and `max_length` separately
5. After loop: append `min_length` then `max_length` (only if both exist)
6. All other constraints go into the list directly

> Constraints are handled via config. If new edge cases arise, update `SKIP_CONSTRAINT_NAMES` or add specific handlers — no core logic change needed.

#### 5c — Allowed Values

If `allowed_values` exists in source, copy only the `value` from each entry:

```python
[{"value": obj["value"]} for obj in source_allowed_values]
```

#### 5d — Remaining Fields

```python
GLOBAL_SKIP_KEYS = {"id", "attachment", "attachments"}
SKIP_UDF_DETAIL_KEYS = {"type"}
SKIP_NULL_VALUE_FIELDS = {"sub_module"}
```

For each key in source UDF details:
1. Skip if key is in `GLOBAL_SKIP_KEYS`, `SKIP_UDF_DETAIL_KEYS`, or already set in payload
2. If value is `None`:
   - Key in `SKIP_NULL_VALUE_FIELDS` → skip entirely
   - Else → include as `None`
3. If value is a string/number → copy directly
4. If value is a dict/object → try to extract by first matching key from `["internal_name", "name"]`
   - If found: `{matched_key: value}`
   - If extraction fails: copy the whole object as-is

#### 5e — Criteria Detection

After fetching UDF details, check if any constraint has `constraint_name == "criteria"`. If so, flag this UDF for the summary (criteria needs manual migration). The UDF still gets migrated — only the criteria constraint is skipped from the payload.

### Step 6 — Create UDF on Target

```
POST /udf_fields
Body: {"udf_field": <payload>}
```

- Success: console shows `[OK] Display Name -> field_key`
- Failure: console shows `[FAIL] Display Name` — payload + API response logged to debug log only
- Continue on failure (do NOT abort)

### Step 7 — Summary

Console output format:

```
==================================================
UDF Migration Complete: 8 / 12 migrated successfully

Failed (2):
  - Custom Priority  (Single Line)
  - Risk Score  (Numeric Field)

Unsupported — migrate manually (1):
  - Custom Calc  (NEW_TYPE)

Has criteria constraint — migrate criteria manually (1):
  - Filtered Field  (Pick List)
==================================================
```

---

## 3. Logging Rules

| Destination | What gets logged |
|---|---|
| Console + `.log` file | Success/fail per UDF + final summary. Clean and crisp. |
| `_debug.log` file | Full detail — payloads, API responses, intermediate processing steps. |

---

## 4. UDF Field Type Config (`udf_config.py`)

Used for field key generation when source key starts with `udf_`.  
`max_length` is the total allowed length of the field key (prefix + name).  
If a field type is NOT in this map → **unsupported** — log error and skip.

| Field Type | Prefix | Max Length |
|---|---|---|
| Single Line | `txt_` | 12 |
| Multi Line | `txt_` | 12 |
| Numeric Field | `num_` | 15 |
| Pick List | `txt_` | 12 |
| Multi Select | `txt_` | 12 |
| Date/Time Field | `date_` | 15 |
| Datestamp | `dt_` | 12 |
| ADD | `add_` | 14 |
| SUBSTRACT | `sub_` | 14 |
| Boolean | `bool_` | 17 |
| Email | `txt_` | 12 |
| Multi Email | `txt_` | 12 |
| Phone | `txt_` | 12 |
| Currency | `dbl_` | 12 |
| Decimal | `dbl_` | 12 |
| Percent | `dbl_` | 12 |
| Url | `txt_` | 12 |
| Auto Number Field | `txt_` | 12 |
| Reference Entity | `ref_` | 12 |
| Multi Select Reference Entity | `mref_` | 12 |
| Check Box | `txt_` | 12 |
| Radio Button | `txt_` | 12 |
| Decision Box | `bool_` | 17 |
| IP Address | `txt_` | 12 |
| attachment | `att_` | 12 |

---

## 5. Skip / Allow Keys (`udf_config.py`)

| Constant | Values | Purpose |
|---|---|---|
| `GLOBAL_SKIP_KEYS` | `id`, `attachment`, `attachments` | Always omitted when building payloads |
| `ALLOWED_CONSTRAINT_KEYS` | `constraint_name`, `constraint_value` | Only these keys are copied from constraint objects |
| `SKIP_CONSTRAINT_NAMES` | `criteria`, `regex`, `digits`, `unique_collection`, `picklist`, `lower_case`, `editable`, `collection` | Constraint names to skip entirely |
| `SKIP_UDF_DETAIL_KEYS` | `type` | Keys in UDF detail response to skip |
| `SKIP_NULL_VALUE_FIELDS` | `sub_module` | If value is null for these keys, omit from payload |
| `UDF_FIELD_KEY_REGEX` | `[a-zA-Z0-9]` | Characters allowed in generated field keys |

---

## 6. Key Behavioural Decisions

| Topic | Decision | Why |
|---|---|---|
| Abort on failure | **No** — continue and log | Per-UDF pass/fail + summary at end |
| Legacy `udf_` keys | Always process and regenerate proper key | Covers all legacy auto-generated keys |
| field_key per module | **request only** — problem/change skip field_key | API assigns key for problem/change; use `module: {internal_name}` |
| Unsupported field type | **Skip UDF, list in summary** | Don't abort; user can migrate manually |
| Criteria constraints | **Skip from payload, flag in summary** | Criteria may contain IDs; needs manual migration |

---

## 7. API Endpoints Used

| Endpoint | Method | Purpose |
|---|---|---|
| `{base}/app/{portal}/api/v3/{module_plural}/_metainfo` | GET | Get UDF field list for a module |
| `{base}/app/{portal}/api/v3/udf_fields/{id}` | GET | Get full UDF field details |
| `{base}/app/{portal}/api/v3/udf_fields` | POST | Create UDF field on target |

import json
import re

from src.modules.logger import logger
from src.config.constants import MODULE_CONFIG
from src.config.template_config import (
    ALLOWED_TEMPLATE_KEYS,
    SKIP_LAYOUT_KEYS,
    SKIP_SECTION_KEYS,
    SKIP_FIELD_KEYS,
    DEFAULT_VALUE_EXTRACT_KEYS,
    PAGE_SIZE,
    UNSUPPORTED_FIELD_REASONS,
)
from src.config.udf_config import GLOBAL_SKIP_KEYS
from src.modules.udf_migration import (
    _fetch_udf_details,
    _build_udf_payload,
    _create_udf_on_target,
)
from src.services.udf_service import _fetch_udf_metadata
from src.services.template_service import (
    get_template_module_config,
    fetch_all_templates,
    resolve_by_ids,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_template_migration(source_client, target_client, module, selected_templates):
    """Orchestrate full template migration for a given module.

    Args:
        selected_templates: List of template dicts (each with 'id' and 'name').
                           Callers (CLI or GUI) are responsible for collecting
                           user selection.
    """
    try:
        mod_cfg = get_template_module_config(module)
        if mod_cfg is None:
            return

        logger.info(f"Starting Template migration for module: {module}")

        templates = selected_templates

        if not templates:
            logger.warn("No templates to migrate.")
            return

        logger.info(f"Templates to migrate: {len(templates)}")

        udf_map, source_udfs = _build_udf_field_map(
            source_client, target_client,
            mod_cfg["entity_plural"], mod_cfg["udf_field_holder"],
        )
        if udf_map is None:
            return

        results = {"passed": [], "failed": [], "auto_created_udfs": []}
        skip_fields = set()  # grows as unsupported fields are detected

        for tpl in templates:
            _migrate_single_template(
                source_client, target_client, tpl, mod_cfg,
                udf_map, source_udfs, module, results, skip_fields,
            )

        _print_summary(results, len(templates))

    except Exception as exc:
        logger.error(f"Template migration failed with unexpected error: {exc}")
        logger.debug(f"Exception details: {type(exc).__name__}: {exc}")
        import traceback
        logger.debug(traceback.format_exc())





# ---------------------------------------------------------------------------
# UDF field map
# ---------------------------------------------------------------------------

def _build_udf_field_map(source_client, target_client, entity_plural, udf_holder):
    """Build source_key → target_key UDF mapping by display_name.

    Returns (udf_map, source_udfs) or (None, None) on failure.
    """
    source_udfs = _fetch_udf_metadata(source_client, entity_plural, udf_holder, "source")
    target_udfs = _fetch_udf_metadata(target_client, entity_plural, udf_holder, "target")

    if source_udfs is None or target_udfs is None:
        logger.error("Failed to fetch UDF metadata — cannot build field map")
        return None, None

    target_by_display = {
        obj.get("display_name"): key for key, obj in target_udfs.items()
    }

    udf_map = {}
    for src_key, src_obj in source_udfs.items():
        display_name = src_obj.get("display_name", "")
        if display_name in target_by_display:
            udf_map[src_key] = target_by_display[display_name]

    logger.debug(f"UDF map: {len(udf_map)} matched of {len(source_udfs)} source UDFs")
    return udf_map, source_udfs


# ---------------------------------------------------------------------------
# Single template migration
# ---------------------------------------------------------------------------

def _migrate_single_template(source_client, target_client, tpl, mod_cfg,
                              udf_map, source_udfs, module, results, skip_fields):
    """Fetch, trim, and create one template on the target."""
    tpl_id = tpl["id"]
    tpl_name = tpl.get("name", f"ID:{tpl_id}")
    tpl_singular = mod_cfg["template_entity_singular"]
    tpl_plural = mod_cfg["template_entity_plural"]
    udf_holder = mod_cfg["udf_field_holder"]

    logger.debug(f"Processing template: {tpl_name} ({tpl_id})")

    root = _fetch_template_root(source_client, tpl_plural, tpl_singular, tpl_id)
    if root is None:
        logger.error(f"  [FAIL] {tpl_name} — could not fetch template data")
        results["failed"].append(tpl_name)
        return

    tpl_name = root.get("name", tpl_name)

    layouts = _fetch_template_layouts(source_client, tpl_plural, tpl_id)
    if layouts is None:
        logger.error(f"  [FAIL] {tpl_name} — could not fetch layouts")
        results["failed"].append(tpl_name)
        return

    # --- Pre-check: skip if template contains fields known to be unsupported ---
    if skip_fields:
        hit = _find_unsupported_fields_in_layouts(layouts, skip_fields)
        if hit:
            reasons = sorted({UNSUPPORTED_FIELD_REASONS[f] for f in hit})
            tag = ", ".join(reasons)
            logger.error(f"  [SKIP] {tpl_name} — [{tag}]")
            results["failed"].append((tpl_name, tag))
            return

    trimmed_root = _trim_template_root(root)
    trimmed_layouts = _trim_layouts(
        layouts, udf_map, source_udfs, udf_holder,
        source_client, target_client, module, results,
    )
    trimmed_root["layouts"] = trimmed_layouts

    _create_template(
        target_client, tpl_plural, tpl_singular,
        trimmed_root, tpl_name, results, skip_fields,
    )


# ---------------------------------------------------------------------------
# Fetch template data
# ---------------------------------------------------------------------------

def _fetch_template_root(client, tpl_plural, tpl_singular, tpl_id):
    """GET /{tpl_plural}/{id}/_get_template_with_layout"""
    try:
        resp = client.get(f"{tpl_plural}/{tpl_id}/_get_template_with_layout")
        if resp.status_code != 200:
            logger.debug(f"  Template root fetch failed — HTTP {resp.status_code}")
            return None
        return resp.json().get(tpl_singular)
    except Exception as exc:
        logger.debug(f"  Template root fetch error: {exc}")
        return None


def _fetch_template_layouts(client, tpl_plural, tpl_id):
    """GET /{tpl_plural}/{id}/layouts"""
    try:
        resp = client.get(f"{tpl_plural}/{tpl_id}/layouts")
        if resp.status_code != 200:
            logger.debug(f"  Template layouts fetch failed — HTTP {resp.status_code}")
            return None
        return resp.json().get("layouts")
    except Exception as exc:
        logger.debug(f"  Template layouts fetch error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Trim and transform
# ---------------------------------------------------------------------------

def _trim_template_root(raw):
    """Keep only ALLOWED_TEMPLATE_KEYS; reduce service_category to {name}."""
    trimmed = {}
    for key in ALLOWED_TEMPLATE_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if key == "service_category" and isinstance(value, dict):
            value = {"name": value.get("name")}
        trimmed[key] = value
    return trimmed


def _trim_layouts(raw_layouts, udf_map, source_udfs, udf_holder,
                  source_client, target_client, module, results):
    """Trim every layout in the list."""
    return [
        _trim_layout(layout, udf_map, source_udfs, udf_holder,
                      source_client, target_client, module, results)
        for layout in (raw_layouts or [])
    ]


def _trim_layout(raw, udf_map, source_udfs, udf_holder,
                 source_client, target_client, module, results):
    """Strip ids/globals, clean help_text, rebuild sections."""
    skip = GLOBAL_SKIP_KEYS | SKIP_LAYOUT_KEYS | {"id", "sections"}
    trimmed = {}

    for key, value in raw.items():
        if key in skip:
            continue
        if key == "help_text" and isinstance(value, list):
            value = [
                {k: v for k, v in entry.items() if k not in GLOBAL_SKIP_KEYS}
                for entry in value
            ]
        trimmed[key] = value

    trimmed["sections"] = [
        _trim_section(s, udf_map, source_udfs, udf_holder,
                      source_client, target_client, module, results)
        for s in (raw.get("sections") or [])
    ]
    return trimmed


def _trim_section(raw, udf_map, source_udfs, udf_holder,
                  source_client, target_client, module, results):
    """Strip ids/globals, rebuild fields."""
    skip = GLOBAL_SKIP_KEYS | SKIP_SECTION_KEYS | {"id", "fields"}
    trimmed = {k: v for k, v in raw.items() if k not in skip}

    trimmed["fields"] = [
        _trim_field(f, udf_map, source_udfs, udf_holder,
                    source_client, target_client, module, results)
        for f in (raw.get("fields") or [])
    ]
    return trimmed


def _trim_field(raw, udf_map, source_udfs, udf_holder,
                source_client, target_client, module, results):
    """UDF name mapping, default_value extraction, scopings cleanup, copy rest."""
    skip = GLOBAL_SKIP_KEYS | SKIP_FIELD_KEYS
    trimmed = {}

    field_name = raw.get("name", "")
    udf_prefix = f"{udf_holder}."
    if field_name.startswith(udf_prefix):
        src_key = field_name[len(udf_prefix):]
        target_key = _resolve_udf_key(
            src_key, udf_map, source_udfs,
            source_client, target_client, module, results,
        )
        field_name = f"{udf_prefix}{target_key}"
    trimmed["name"] = field_name

    if raw.get("default_value") is not None:
        trimmed["default_value"] = _process_default_value(raw["default_value"])

    if raw.get("scopings") is not None:
        trimmed["scopings"] = [
            {k: v for k, v in s.items() if k not in GLOBAL_SKIP_KEYS}
            for s in raw["scopings"]
        ]

    for key, value in raw.items():
        if key in skip or key in trimmed:
            continue
        trimmed[key] = value

    return trimmed


def _process_default_value(entries):
    """Transform default_value array with Deluge-style extraction logic."""
    result = []
    for entry in entries:
        if entry is None:
            result.append(None)
            continue

        value = entry.get("value") if isinstance(entry, dict) else entry

        if value is None:
            result.append({"value": None})
        elif isinstance(value, (str, int, float, bool)):
            result.append({"value": value})
        elif isinstance(value, dict):
            result.append({"value": _extract_default_object(value)})
        else:
            result.append({"value": value})
    return result


def _extract_default_object(obj):
    """Try to pull the first recognized key from a default-value object."""
    for key in DEFAULT_VALUE_EXTRACT_KEYS:
        if key in obj and obj[key] is not None:
            return {key: obj[key]}
    return obj


# ---------------------------------------------------------------------------
# UDF auto-creation (on-demand during field processing)
# ---------------------------------------------------------------------------

def _resolve_udf_key(src_key, udf_map, source_udfs,
                     source_client, target_client, module, results):
    """Return the target UDF key; auto-create on target if not mapped yet."""
    if src_key in udf_map:
        return udf_map[src_key]

    logger.warn(f"  UDF '{src_key}' missing on target — auto-creating")

    src_info = source_udfs.get(src_key)
    if src_info is None:
        logger.error(f"  UDF '{src_key}' not found in source metadata")
        return src_key

    udf_id = src_info.get("id")
    display_name = src_info.get("display_name", src_key)
    field_type = src_info.get("field_type", "")

    details = _fetch_udf_details(source_client, udf_id)
    if details is None:
        logger.error(f"  Could not fetch details for UDF '{display_name}'")
        return src_key

    payload = _build_udf_payload(details, src_key, module)
    if payload is None:
        logger.error(f"  Unsupported type for UDF '{display_name}' — skipping auto-creation")
        return src_key

    new_key = _create_udf_on_target(target_client, payload, display_name)
    if not new_key:
        return src_key

    udf_map[src_key] = new_key
    results["auto_created_udfs"].append({
        "display_name": display_name,
        "field_type": field_type,
        "new_key": new_key,
    })
    return new_key


# ---------------------------------------------------------------------------
# Create template on target
# ---------------------------------------------------------------------------

def _create_template(client, tpl_plural, tpl_singular, payload_body, tpl_name, results, skip_fields):
    """POST /{tpl_plural} with trimmed payload."""
    payload = {tpl_singular: payload_body}
    try:
        resp = client.post(tpl_plural, payload)
        data = resp.json()

        if data.get(tpl_singular) is not None:
            logger.success(f"  [OK] {tpl_name}")
            results["passed"].append(tpl_name)
            return

        # --- Detect unsupported fields from the error response ---
        detected = _detect_unsupported_fields(data)
        if detected:
            skip_fields.update(detected)
            reasons = sorted({UNSUPPORTED_FIELD_REASONS[f] for f in detected})
            tag = ", ".join(reasons)
            logger.error(f"  [FAIL] {tpl_name} — [{tag}]")
            logger.debug(f"  Detected unsupported fields: {detected}")
        else:
            logger.error(f"  [FAIL] {tpl_name}")

        logger.debug(f"  POST URL: {tpl_plural}")
        logger.debug(f"  POST payload: {json.dumps(payload, default=str)}")
        logger.debug(f"  Response: {json.dumps(data, default=str)}")
        results["failed"].append((tpl_name, tag) if detected else tpl_name)

    except Exception as exc:
        logger.error(f"  [FAIL] {tpl_name}")
        logger.debug(f"  POST payload: {json.dumps(payload, default=str)}")
        logger.debug(f"  Exception: {exc}")
        results["failed"].append(tpl_name)


# ---------------------------------------------------------------------------
# Unsupported field detection
# ---------------------------------------------------------------------------

def _detect_unsupported_fields(response_data):
    """Parse the API error response and return set of unsupported field names.

    Recursively collects all string "message" values from the nested error
    response, then extracts field names from the '[field_name]' pattern.
    Only returns fields that exist in UNSUPPORTED_FIELD_REASONS.
    Returns empty set if nothing matched or parsing fails.
    """
    detected = set()
    try:
        for msg_text in _collect_messages(response_data):
            for field_name in re.findall(r"\[(\w+)\]", msg_text):
                if field_name in UNSUPPORTED_FIELD_REASONS:
                    detected.add(field_name)
    except Exception:
        pass
    return detected


def _collect_messages(obj):
    """Recursively walk a nested dict/list and yield all string 'message' values."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "message" and isinstance(value, str):
                yield value
            else:
                yield from _collect_messages(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _collect_messages(item)


def _find_unsupported_fields_in_layouts(layouts, skip_fields):
    """Scan raw layouts for field names present in skip_fields. Return matched set."""
    found = set()
    for layout in (layouts or []):
        for section in layout.get("sections", []):
            for field in section.get("fields", []):
                name = field.get("name", "")
                if name in skip_fields:
                    found.add(name)
    return found


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(results, total):
    """Print migration results to console."""
    passed = len(results["passed"])
    failed = len(results["failed"])
    auto_udfs = results["auto_created_udfs"]

    logger.info("")
    logger.info("=" * 50)

    if failed == 0:
        logger.success(f"Template Migration Complete: {passed} / {total} migrated successfully")
    else:
        logger.warn(f"Template Migration Complete: {passed} / {total} migrated successfully")

    if results["failed"]:
        logger.info("")
        logger.error(f"Failed ({failed}):")
        for entry in results["failed"]:
            if isinstance(entry, tuple):
                name, reason = entry
                logger.error(f"  - {name}  [{reason}]")
            else:
                logger.error(f"  - {entry}")

    if auto_udfs:
        logger.info("")
        logger.info(f"UDFs auto-created during migration ({len(auto_udfs)}):")
        for u in auto_udfs:
            logger.info(f"  - {u['display_name']}  ({u['field_type']}) -> {u['new_key']}")

    logger.info("=" * 50)

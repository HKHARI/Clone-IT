import re
import json

from src.modules.logger import logger
from src.config.constants import MODULE_CONFIG
from src.config.udf_config import (
    FIELD_KEY_SUPPORTED_MODULES,
    GLOBAL_SKIP_KEYS,
    ALLOWED_CONSTRAINT_KEYS,
    SKIP_CONSTRAINT_NAMES,
    SKIP_UDF_DETAIL_KEYS,
    SKIP_NULL_VALUE_FIELDS,
    NESTED_OBJECT_EXTRACT_KEYS,
    UDF_FIELD_TYPE_CONFIG,
)
from src.services.udf_service import get_udf_context, _fetch_udf_metadata


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_udf_migration(source_client, target_client, module, selected_udfs):
    """Orchestrate the full UDF migration for a given module.

    Args:
        selected_udfs: List of UDF dicts to migrate (each with a "key" field).
                       Callers (CLI or GUI) are responsible for collecting selection
                       via the generic item loader.
    """
    logger.info(f"Starting UDF migration for module: {module}")

    try:
        # Fetch and compare UDFs via service
        ctx = get_udf_context(source_client, target_client, module)
        if ctx is None:
            return

        to_migrate = ctx["to_migrate"]

        if not to_migrate:
            logger.success("All source UDFs already exist on target. Nothing to migrate.")
            return

        # Extract keys from item dicts
        selected_keys = {item["key"] for item in selected_udfs}

        selected = [u for u in to_migrate if u["key"] in selected_keys]

        if not selected:
            logger.warn("No UDFs selected for migration.")
            return

        # Migrate each UDF
        results = {"passed": [], "failed": [], "unsupported": [], "criteria": []}

        for udf_entry in selected:
            outcome = _migrate_single_udf(source_client, target_client, udf_entry, module)
            results[outcome["status"]].append(udf_entry)
            if outcome.get("has_criteria"):
                results["criteria"].append(udf_entry)

        _print_summary(results, len(selected))

    except Exception as exc:
        logger.error(f"UDF migration failed with unexpected error: {exc}")
        logger.debug(f"Exception details: {type(exc).__name__}: {exc}")
        import traceback
        logger.debug(traceback.format_exc())




# ---------------------------------------------------------------------------
# 3.4–3.6 — Migrate a single UDF
# ---------------------------------------------------------------------------

def _migrate_single_udf(source_client, target_client, udf_entry, module):
    """Fetch details, build payload, create on target.

    Returns dict: {"status": "passed"|"failed"|"unsupported", "has_criteria": bool}
    """
    display_name = udf_entry["display_name"]
    udf_id = udf_entry["id"]
    src_key = udf_entry["key"]

    logger.debug(f"Processing UDF: {display_name} ({src_key})")

    # 3.4 — Fetch full UDF details from source
    src_details = _fetch_udf_details(source_client, udf_id)
    if src_details is None:
        logger.error(f"  [FAIL] {display_name} — could not fetch details")
        return {"status": "failed", "has_criteria": False}

    # Check for criteria constraints
    has_criteria = _has_criteria(src_details.get("constraints"))

    # 3.5 — Build creation payload
    payload = _build_udf_payload(src_details, src_key, module)
    if payload is None:
        logger.error(f"  [SKIP] {display_name} — unsupported field type: {udf_entry['field_type']}")
        return {"status": "unsupported", "has_criteria": has_criteria}

    # 3.6 — Create on target
    success = _create_udf_on_target(target_client, payload, display_name)
    status = "passed" if success else "failed"
    return {"status": status, "has_criteria": has_criteria}


def _fetch_udf_details(client, udf_id):
    """GET /udf_fields/{id} — fetch full UDF field details."""
    try:
        response = client.get(f"udf_fields/{udf_id}")
        if response.status_code != 200:
            logger.debug(f"  UDF details request failed — HTTP {response.status_code}")
            return None
        return response.json().get("udf_field")
    except Exception as exc:
        logger.debug(f"  UDF details request error: {exc}")
        return None


def _create_udf_on_target(client, payload, display_name):
    """POST /udf_fields — create UDF on target instance.

    Returns the new field_key string on success (truthy), None on failure (falsy).
    """
    try:
        response = client.post("udf_fields", {"udf_field": payload})
        data = response.json()

        if data.get("udf_field") is not None:
            new_key = data["udf_field"].get("field_key", "?")
            logger.success(f"  [OK] {display_name} -> {new_key}")
            return new_key

        logger.error(f"  [FAIL] {display_name}")
        logger.debug(f"  Payload sent: {json.dumps(payload, default=str)}")
        logger.debug(f"  Response: {json.dumps(data, default=str)}")
        return None

    except Exception as exc:
        logger.error(f"  [FAIL] {display_name}")
        logger.debug(f"  Payload sent: {json.dumps(payload, default=str)}")
        logger.debug(f"  Exception: {exc}")
        return None


# ---------------------------------------------------------------------------
# 3.5 — Build UDF creation payload
# ---------------------------------------------------------------------------

def _build_udf_payload(src_details, src_key, module):
    """Transform source UDF details into a creation payload for the target."""
    payload = {}
    skip_field_key = module not in FIELD_KEY_SUPPORTED_MODULES

    # 3.5a — Field key generation (request module only)
    if not skip_field_key and src_key.startswith("udf_"):
        new_key = _generate_field_key(src_details)
        if new_key is None:
            return None
        src_details["field_key"] = new_key
        logger.debug(f"  Field key regenerated: {src_key} -> {new_key}")

    # 3.5b — Constraints
    if src_details.get("constraints") is not None:
        payload["constraints"] = _process_constraints(src_details["constraints"])

    # 3.5c — Allowed values
    if src_details.get("allowed_values") is not None:
        payload["allowed_values"] = [
            {"value": v.get("value")} for v in src_details["allowed_values"]
        ]

    # 3.5d — Remaining fields
    for key, value in src_details.items():
        if key in GLOBAL_SKIP_KEYS or key in SKIP_UDF_DETAIL_KEYS:
            continue
        if key in payload:
            continue
        if skip_field_key and key == "field_key":
            continue

        if value is None:
            if key in SKIP_NULL_VALUE_FIELDS:
                continue
            payload[key] = None
        elif isinstance(value, (str, int, float, bool)):
            payload[key] = value
        elif isinstance(value, list):
            payload[key] = value
        elif isinstance(value, dict):
            payload[key] = _extract_nested_object(value)
        else:
            payload[key] = value

    return payload


def _generate_field_key(src_details):
    """Generate a proper field key for legacy udf_ prefixed keys.

    Rules:
      - Lowercase the UDF name
      - Keep only alphanumeric chars, replace rest with _
      - No consecutive underscores, no leading/trailing _ on name portion
      - Prepend the type prefix (e.g. txt_, num_)
      - Total key length must not exceed the type's max_length
      - Unsupported field type → return None
    """
    field_type = src_details.get("field_type", "")
    type_cfg = UDF_FIELD_TYPE_CONFIG.get(field_type)

    if type_cfg is None:
        return None

    prefix = type_cfg["prefix"]
    max_length = type_cfg["max_length"]

    sanitized = re.sub(r"[^a-zA-Z0-9]", "_", (src_details.get("name") or "").lower())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")

    new_key = prefix + sanitized
    if len(new_key) > max_length:
        new_key = new_key[:max_length].rstrip("_")

    return new_key


def _has_criteria(constraints):
    """Check if any constraint has constraint_name == 'criteria' with a non-empty value."""
    if not constraints:
        return False
    for c in constraints:
        if c.get("constraint_name") == "criteria":
            val = c.get("constraint_value")
            if val and val not in ([], {}, "", None, False):
                return True
    return False


def _process_constraints(src_constraints):
    """Filter constraints: skip blacklisted, keep only allowed keys,
    include min/max_length only as a valid pair (both non-null, both >= 0, max > min)."""
    skip = SKIP_CONSTRAINT_NAMES | GLOBAL_SKIP_KEYS
    length_pair = {}
    result = []

    for c in src_constraints:
        name = c.get("constraint_name", "")
        if name in skip:
            continue
        cleaned = {k: c.get(k) for k in ALLOWED_CONSTRAINT_KEYS}
        if name in ("min_length", "max_length"):
            length_pair[name] = cleaned
        else:
            result.append(cleaned)

    if _valid_length_pair(length_pair):
        result.append(length_pair["min_length"])
        result.append(length_pair["max_length"])

    return result


def _valid_length_pair(pair):
    """Return True only if both min_length and max_length exist with values >= 0 and max > min."""
    if "min_length" not in pair or "max_length" not in pair:
        return False
    try:
        min_val = int(pair["min_length"].get("constraint_value", -1))
        max_val = int(pair["max_length"].get("constraint_value", -1))
        return min_val >= 0 and max_val >= 0 and max_val > min_val
    except (ValueError, TypeError):
        return False


def _extract_nested_object(obj):
    """For dict values, try to extract by internal_name or name.
    Falls back to returning the whole object."""
    for key in NESTED_OBJECT_EXTRACT_KEYS:
        if key in obj and obj[key] is not None:
            return {key: obj[key]}
    return obj


# ---------------------------------------------------------------------------
# 3.7 — Summary
# ---------------------------------------------------------------------------

def _print_summary(results, total):
    """Print migration results summary."""
    passed = len(results["passed"])
    failed = len(results["failed"])
    unsupported = len(results["unsupported"])

    logger.info("")
    logger.info("=" * 50)

    if failed == 0 and unsupported == 0:
        logger.success(f"UDF Migration Complete: {passed} / {total} migrated successfully")
    else:
        logger.warn(f"UDF Migration Complete: {passed} / {total} migrated successfully")

    if results["failed"]:
        logger.info("")
        logger.error(f"Failed ({failed}):")
        for u in results["failed"]:
            logger.error(f"  - {u['display_name']}  ({u['field_type']})")

    if results["unsupported"]:
        logger.info("")
        logger.warn(f"Unsupported — migrate manually ({unsupported}):")
        for u in results["unsupported"]:
            logger.warn(f"  - {u['display_name']}  ({u['field_type']})")

    if results["criteria"]:
        logger.info("")
        logger.warn(f"Has criteria constraint — migrate criteria manually ({len(results['criteria'])}):")
        for u in results["criteria"]:
            logger.warn(f"  - {u['display_name']}  ({u['field_type']})")

    logger.info("=" * 50)

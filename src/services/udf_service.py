"""UDF service — shared UDF migration logic.

Provides fetch, compare, and migrate functions used by both
CLI (udf_migration.py) and Web UI (app.py).
"""

from src.modules.logger import logger
from src.config.constants import MODULE_CONFIG


def get_udf_context(source_client, target_client, module):
    """Fetch UDF metadata from both instances and compute what needs migration.

    Returns:
        dict with keys:
            source_udfs (dict): raw source UDF metadata
            target_udfs (dict): raw target UDF metadata
            to_migrate (list[dict]): UDFs missing on target
            existing_count (int): UDFs already present on target
        or None on failure.
    """
    mod_cfg = MODULE_CONFIG.get(module)
    if mod_cfg is None:
        logger.error(f"No module configuration found for '{module}'")
        return None

    entity_plural = mod_cfg["entity_plural"]
    udf_holder = mod_cfg["udf_field_holder"]

    source_udfs = _fetch_udf_metadata(source_client, entity_plural, udf_holder, "source")
    target_udfs = _fetch_udf_metadata(target_client, entity_plural, udf_holder, "target")

    if source_udfs is None or target_udfs is None:
        logger.error("Failed to fetch UDF metadata. Aborting.")
        return None

    target_display_map = {
        obj["display_name"]: key for key, obj in target_udfs.items()
    }

    to_migrate = []
    existing_count = 0

    for src_key, src_obj in source_udfs.items():
        display_name = src_obj.get("display_name", "")
        if display_name in target_display_map:
            existing_count += 1
        else:
            to_migrate.append({
                "key": src_key,
                "id": src_obj.get("id"),
                "display_name": display_name,
                "field_type": src_obj.get("field_type", ""),
            })

    logger.info(
        f"Source: {len(source_udfs)} | Target: {len(target_udfs)} | "
        f"Exist: {existing_count} | To migrate: {len(to_migrate)}"
    )

    return {
        "source_udfs": source_udfs,
        "target_udfs": target_udfs,
        "to_migrate": to_migrate,
        "existing_count": existing_count,
    }


def _fetch_udf_metadata(client, entity_plural, udf_holder, label):
    """GET /{entity_plural}/_metainfo and extract UDF fields."""
    logger.debug(f"[{label}] Fetching UDF metadata...")
    try:
        response = client.get(f"{entity_plural}/_metainfo")
        if response.status_code != 200:
            logger.error(f"[{label}] Metainfo request failed — HTTP {response.status_code}")
            return None

        data = response.json()
        udf_section = data.get("metainfo", {}).get("fields", {}).get(udf_holder)

        if udf_section is None or udf_section.get("fields") is None:
            logger.debug(f"[{label}] No UDF fields found")
            return {}

        fields = udf_section["fields"]
        logger.debug(f"[{label}] Found {len(fields)} UDF fields")
        return fields

    except Exception as exc:
        logger.error(f"[{label}] Failed to fetch UDF metadata: {exc}")
        return None

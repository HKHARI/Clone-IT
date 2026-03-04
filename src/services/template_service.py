"""Template service — shared template migration logic.

Provides fetch and listing functions used by both
CLI (template_migration.py) and Web UI (app.py).
"""

import json

from src.modules.logger import logger
from src.config.constants import MODULE_CONFIG


def get_template_module_config(module):
    """Return the module config for template migration, or None if unsupported."""
    mod_cfg = MODULE_CONFIG.get(module)
    if mod_cfg is None or "template_entity_singular" not in mod_cfg:
        logger.error(f"No template module configuration found for '{module}'")
        return None
    return mod_cfg


def fetch_all_templates(source_client, mod_cfg, include_inactive=False):
    """Fetch all templates from the source, optionally filtering out inactive ones.

    Returns:
        list of template dicts, each with at least 'id' and 'name' keys.
    """
    tpl_plural = mod_cfg["template_entity_plural"]
    search_criteria = mod_cfg.get("template_list_criteria")

    templates = _paginate_templates(source_client, tpl_plural, search_criteria)

    if not include_inactive:
        templates = [t for t in templates if not t.get("inactive", False)]

    logger.info(f"Found {len(templates)} template(s) on source")
    return templates


def resolve_by_ids(raw_ids):
    """Convert a comma-separated ID string to a list of template dicts."""
    ids = [i.strip() for i in raw_ids.split(",") if i.strip()]
    return [{"id": tid, "name": f"ID:{tid}"} for tid in ids]


def _paginate_templates(client, template_entity_plural, search_criteria=None):
    """Paginate through GET /{template_entity_plural} to collect all templates."""
    templates = []
    start_index = 1
    row_count = 100

    while True:
        list_info_obj = {
            "row_count": row_count,
            "start_index": start_index,
            "get_total_count": True,
            "sort_fields": [{"field": "name", "order": "asc"}],
        }
        if search_criteria:
            list_info_obj["search_criteria"] = search_criteria
        list_info = {"list_info": list_info_obj}
        try:
            resp = client.get(
                template_entity_plural,
                params={"input_data": json.dumps(list_info)},
            )
            if resp.status_code != 200:
                logger.error(f"Failed to fetch templates — HTTP {resp.status_code}")
                return []

            data = resp.json()
            batch = data.get(template_entity_plural, [])
            templates.extend(batch)

            if not data.get("list_info", {}).get("has_more_rows", False):
                break
            start_index += row_count

        except Exception as exc:
            logger.error(f"Error fetching templates: {exc}")
            return []

    return templates

"""Migration service — shared migration orchestration logic.

Provides migration type/module choices, item loading, and delegates to
the appropriate migration handler. Used by both CLI and Web UI.
"""

from src.config.constants import SUPPORTED_MIGRATIONS
from src.modules.udf_migration import run_udf_migration
from src.modules.template_migration import run_template_migration
from src.services.udf_service import get_udf_context
from src.services.template_service import (
    get_template_module_config,
    fetch_all_templates,
    resolve_by_ids,
)


# ---------------------------------------------------------------------------
# Handler registry — maps migration_type → handler function
# ---------------------------------------------------------------------------

MIGRATION_HANDLERS = {
    "udf": run_udf_migration,
    "template": run_template_migration,
}


# ---------------------------------------------------------------------------
# Item loader registry — maps loader key → function(src, tgt, module, **opts)
# Each returns a list of item dicts.
# ---------------------------------------------------------------------------

def _load_udf_items(source_client, target_client, module, **opts):
    """Fetch UDFs that need migration."""
    ctx = get_udf_context(source_client, target_client, module)
    if ctx is None:
        return []
    return ctx["to_migrate"] or []


def _load_template_items(source_client, target_client, module, **opts):
    """Fetch templates from source."""
    mod_cfg = get_template_module_config(module)
    if mod_cfg is None:
        return []
    include_inactive = opts.get("include_inactive", False)
    return fetch_all_templates(source_client, mod_cfg, include_inactive) or []


ITEM_LOADERS = {
    "load_udfs": _load_udf_items,
    "load_templates": _load_template_items,
}


def load_items(loader_key, source_client, target_client, module, **opts):
    """Generic item loader — resolves the loader key and calls it.

    Args:
        loader_key: Key into ITEM_LOADERS (e.g. "load_udfs").
        opts: Extra options forwarded to the loader (e.g. include_inactive).

    Returns:
        List of item dicts. Empty list on failure.
    """
    loader = ITEM_LOADERS.get(loader_key)
    if loader is None:
        return []
    return loader(source_client, target_client, module, **opts)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_migration_choices():
    """Return a list of {label, value} dicts for all supported migrations."""
    return [
        {"label": cfg["label"], "value": key}
        for key, cfg in SUPPORTED_MIGRATIONS.items()
    ]


def get_module_choices(migration_type):
    """Return a list of {label, value} dicts for modules supported by the migration type."""
    cfg = SUPPORTED_MIGRATIONS.get(migration_type)
    if cfg is None:
        return []
    return [
        {"label": m.capitalize(), "value": m}
        for m in cfg["supported_modules"]
    ]


def get_dependencies(migration_type):
    """Return dependency info for a migration type.

    Returns:
        dict with keys:
            has_deps (bool): whether there are dependencies
            dep_labels (list[str]): human-readable dependency names
    """
    cfg = SUPPORTED_MIGRATIONS.get(migration_type, {})
    deps = cfg.get("dependencies", [])
    dep_labels = [
        SUPPORTED_MIGRATIONS[d]["label"]
        for d in deps
        if d in SUPPORTED_MIGRATIONS
    ]
    return {"has_deps": bool(deps), "dep_labels": dep_labels}


def get_steps(migration_type):
    """Return the steps config for a migration type."""
    cfg = SUPPORTED_MIGRATIONS.get(migration_type, {})
    return cfg.get("steps", [])


def should_show_step(step, current_mode, module):
    """Check whether a step's conditions are met.

    Args:
        step: Step config dict.
        current_mode: Current item_selection mode (e.g. "all", "selected").
        module: Currently selected module (e.g. "request").

    Returns:
        True if step should be shown.
    """
    condition = step.get("condition")
    if condition is None:
        return True
    if "mode_in" in condition:
        if current_mode not in condition["mode_in"]:
            return False
    if "module_in" in condition:
        if module not in condition["module_in"]:
            return False
    return True


# ---------------------------------------------------------------------------
# Run migration
# ---------------------------------------------------------------------------

def run_migration(migration_type, source_client, target_client, module, **kwargs):
    """Execute the migration handler for the given type.

    Any extra keyword arguments (e.g. selected_udfs, selected_templates)
    are forwarded to the handler function.

    Returns:
        True if handler was found and executed, False otherwise.
    """
    handler = MIGRATION_HANDLERS.get(migration_type)
    if handler is None:
        return False
    handler(source_client, target_client, module, **kwargs)
    return True

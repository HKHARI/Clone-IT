ALLOWED_TEMPLATE_KEYS = {
    "name", "comments", "reference_templates", "show_to_requester",
    "task_configuration", "is_service_template", "service_category",
    "is_cost_enabled", "image", "cost_details",
}

SKIP_LAYOUT_KEYS = set()
SKIP_SECTION_KEYS = set()
SKIP_FIELD_KEYS = {"template_id"}

DEFAULT_VALUE_EXTRACT_KEYS = ["email_id", "internal_name", "name", "value"]

PAGE_SIZE = 15

# Fields that the SDP API rejects when a feature is disabled on the target
# instance.  key = field name as it appears in template layouts,
# value = human-readable reason shown in the migration summary.
# Just add a line here to handle new cases — no code changes needed.
UNSUPPORTED_FIELD_REASONS = {
    "assets": "Asset Disabled",
}

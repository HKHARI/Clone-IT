ZOHO_ACCOUNTS_URLS = [
    {"label": "US / Global  — https://accounts.zoho.com", "value": "https://accounts.zoho.com"},
    {"label": "EU           — https://accounts.zoho.eu", "value": "https://accounts.zoho.eu"},
    {"label": "India        — https://accounts.zoho.in", "value": "https://accounts.zoho.in"},
    {"label": "Australia    — https://accounts.zoho.com.au", "value": "https://accounts.zoho.com.au"},
    {"label": "Japan        — https://accounts.zoho.jp", "value": "https://accounts.zoho.jp"},
    {"label": "China        — https://accounts.zoho.com.cn", "value": "https://accounts.zoho.com.cn"},
    {"label": "Canada       — https://accounts.zohocloud.ca", "value": "https://accounts.zohocloud.ca"},
    {"label": "Saudi Arabia — https://accounts.zoho.sa", "value": "https://accounts.zoho.sa"},
]

DEFAULT_REDIRECT_URI = "https://www.zoho.com"

VALIDATION_SUCCESS_CODE = 2000

MODULE_CONFIG = {
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

SUPPORTED_MIGRATIONS = {
    "udf": {
        "label": "UDF Migration",
        "supported_modules": ["request", "problem", "change"],
        "dependencies": [],
        "steps": [
            {
                "key": "selected_udfs",
                "type": "item_selection",
                "label": "UDF Selection",
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
                "label": "Template Selection",
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

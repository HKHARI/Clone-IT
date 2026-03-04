FIELD_KEY_SUPPORTED_MODULES = {"request"}

GLOBAL_SKIP_KEYS = {"id", "attachment", "attachments"}

ALLOWED_CONSTRAINT_KEYS = {"constraint_name", "constraint_value"}

SKIP_CONSTRAINT_NAMES = {
    "criteria",
    "regex",
    "digits",
    "unique_collection",
    "picklist",
    "lower_case",
    "editable",
    "collection",
}

SKIP_UDF_DETAIL_KEYS = {"type"}

SKIP_NULL_VALUE_FIELDS = {"sub_module"}

UDF_FIELD_KEY_REGEX = r"[a-zA-Z0-9]"

NESTED_OBJECT_EXTRACT_KEYS = ["internal_name", "name"]

UDF_FIELD_TYPE_CONFIG = {
    "Single Line":                  {"prefix": "txt_",  "max_length": 12},
    "Multi Line":                   {"prefix": "txt_",  "max_length": 12},
    "Numeric Field":                {"prefix": "num_",  "max_length": 15},
    "Pick List":                    {"prefix": "txt_",  "max_length": 12},
    "Multi Select":                 {"prefix": "txt_",  "max_length": 12},
    "Date/Time Field":              {"prefix": "date_", "max_length": 15},
    "Datestamp":                     {"prefix": "dt_",   "max_length": 12},
    "ADD":                          {"prefix": "add_",  "max_length": 14},
    "SUBSTRACT":                    {"prefix": "sub_",  "max_length": 14},
    "Boolean":                      {"prefix": "bool_", "max_length": 17},
    "Email":                        {"prefix": "txt_",  "max_length": 12},
    "Multi Email":                  {"prefix": "txt_",  "max_length": 12},
    "Phone":                        {"prefix": "txt_",  "max_length": 12},
    "Currency":                     {"prefix": "dbl_",  "max_length": 12},
    "Decimal":                      {"prefix": "dbl_",  "max_length": 12},
    "Percent":                      {"prefix": "dbl_",  "max_length": 12},
    "Url":                          {"prefix": "txt_",  "max_length": 12},
    "Auto Number Field":            {"prefix": "txt_",  "max_length": 12},
    "Reference Entity":             {"prefix": "ref_",  "max_length": 12},
    "Multi Select Reference Entity": {"prefix": "mref_", "max_length": 12},
    "Check Box":                    {"prefix": "txt_",  "max_length": 12},
    "Radio Button":                 {"prefix": "txt_",  "max_length": 12},
    "Decision Box":                 {"prefix": "bool_", "max_length": 17},
    "IP Address":                   {"prefix": "txt_",  "max_length": 12},
    "attachment":                   {"prefix": "att_",  "max_length": 12},
}

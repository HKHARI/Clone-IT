# API Endpoints — SDP On-Demand v3

---

## Common Headers (all requests)

```
Accept: application/vnd.manageengine.sdp.v3+json
Authorization: Zoho-oauthtoken <ACCESS_TOKEN>
Content-Type: application/x-www-form-urlencoded
```

---

## Common Patterns

### `input_data` (form-encoded payload)

All **POST/PUT** bodies are sent as a form-encoded parameter named `input_data`.
All **GET** list endpoints accept `input_data` as a **URL query parameter** (URL-encoded JSON) to pass `list_info`.

### `list_info` object

Used with any **list/get-all** endpoint for pagination, sorting, searching, and field selection.
Pass it inside `input_data` as a URL-encoded query parameter.

```json
{
  "list_info": {
    "row_count": 100,
    "start_index": 1,
    "sort_fields": [
      { "field": "name", "order": "asc" }
    ],
    "get_total_count": true,
    "search_criteria": [
      {
        "field": "<field_name>",
        "condition": "eq",
        "value": "<value>",
        "logical_operator": "and"
      }
    ],
    "fields_required": ["field1", "field2"]
  }
}
```

| Key                | Type    | Description                                                             |
|--------------------|---------|-------------------------------------------------------------------------|
| `row_count`        | number  | Rows to return (max 100)                                                |
| `start_index`      | number  | Starting row index (1-based)                                            |
| `sort_fields`      | array   | Array of `{ "field", "order" }` objects (`asc` / `desc`)               |
| `get_total_count`  | boolean | Return `total_count` in response (default `false`)                      |
| `has_more_rows`    | boolean | _(response only)_ Indicates more pages available                        |
| `total_count`      | number  | _(response only)_ Total matching records (only when `get_total_count`)  |
| `search_criteria`  | array   | Advanced filter — see [search criteria docs](https://www.manageengine.com/products/service-desk/sdpod-v3-api/getting-started/input-data.html#list-info) |
| `fields_required`  | array   | Restrict response to listed fields only                                 |

### `response_status` object

Every response includes a `response_status` array:

```json
{
  "response_status": [
    { "status_code": 2000, "status": "success" }
  ]
}
```

---

## Request Templates

### 1. List Request Templates

- **URL:** `{INSTANCE_URL}/api/v3/request_templates`
- **Method:** `GET`
- **Query Params:** `input_data` with `list_info` (see [Common Patterns](#list_info-object))
- **Example Payload:**
```json
{
  "list_info": {
    "row_count": 10,
    "start_index": 1,
    "get_total_count": true,
    "search_criteria": [
      {
        "field": "is_service_template",
        "condition": "eq",
        "value": false,
        "logical_operator": "and"
      }
    ],
    "sort_fields": [
      { "field": "name", "order": "asc" }
    ]
  }
}
```
- **Response Body:**
```json
{
  "request_templates": [
    {
      "lifecycle": null,
      "image": "incident-icon",
      "inactive": false,
      "comments": "Default template used for new request creation.",
      "workflow": null,
      "is_service_template": false,
      "service_category": null,
      "show_to_requester": true,
      "name": "Default Request",
      "id": "191203000000006655",
      "is_default": true
    }
  ],
  "response_status": [{ "status_code": 2000, "status": "success" }],
  "list_info": { "has_more_rows": false, "total_count": 6, "row_count": 6 }
}
```

---

### 2. Get Template with Layout

- **URL:** `{INSTANCE_URL}/api/v3/request_templates/{template_id}/_get_template_with_layout`
- **Method:** `GET`
- **Request Body:** _None_
- **Response Body:**
```json
{
  "request_template": {
    "name": "Default Template",
    "comments": "...",
    "show_to_requester": true,
    "is_service_template": false,
    "service_category": { "name": "General" },
    "is_cost_enabled": false,
    "task_configuration": {},
    "reference_templates": [],
    "image": null,
    "cost_details": null
  }
}
```

---

### 3. Get Template Layouts

- **URL:** `{INSTANCE_URL}/api/v3/request_templates/{template_id}/layouts`
- **Method:** `GET`
- **Request Body:** _None_
- **Response Body:**
```json
{
  "layouts": [
    {
      "id": "123456",
      "help_text": [
        { "description": "...", "type": "..." }
      ],
      "sections": [
        {
          "id": "789",
          "name": "Details",
          "fields": [
            {
              "name": "subject",
              "template_id": "9119000003009017",
              "default_value": [{ "value": "Default Subject" }],
              "scopings": [{ "scope": "requester", "access": "editable" }]
            },
            {
              "name": "udf_fields.txt_my_field",
              "default_value": [{ "value": { "name": "Option A" } }]
            }
          ]
        }
      ]
    }
  ]
}
```

---

### 4. Create Request Template

- **URL:** `{INSTANCE_URL}/api/v3/request_templates`
- **Method:** `POST`
- **Request Body:** (form-encoded under `input_data`)
```json
{
  "request_template": {
    "name": "Migrated Template",
    "comments": "...",
    "show_to_requester": true,
    "is_service_template": false,
    "service_category": { "name": "General" },
    "layouts": [
      {
        "help_text": [],
        "sections": [
          {
            "name": "Details",
            "fields": [
              {
                "name": "subject",
                "default_value": [{ "value": "Default Subject" }],
                "scopings": [{ "scope": "requester", "access": "editable" }]
              },
              {
                "name": "udf_fields.txt_my_field",
                "default_value": [{ "value": "Option A" }]
              }
            ]
          }
        ]
      }
    ]
  }
}
```
- **Response Body:**
```json
{
  "request_template": {
    "id": "9119000009999999",
    "name": "Migrated Template"
  }
}
```

---

## UDF Fields

### 5. Get Requests Metainfo (UDF field metadata)

- **URL:** `{INSTANCE_URL}/api/v3/requests/_metainfo`
- **Method:** `GET`
- **Request Body:** _None_
- **Response Body:**
```json
{
  "metainfo": {
    "fields": {
      "udf_fields": {
        "fields": {
          "<udf_key>": {
            "id": "90000000012345",
            "display_name": "My Custom Field",
            "field_type": "Single Line"
          }
        }
      }
    }
  }
}
```

---

### 6. Get UDF Field Details

- **URL:** `{INSTANCE_URL}/api/v3/udf_fields/{udf_field_id}`
- **Method:** `GET`
- **Request Body:** _None_
- **Response Body:**
```json
{
  "udf_field": {
    "id": "90000000012345",
    "name": "my_custom_field",
    "display_name": "My Custom Field",
    "field_key": "txt_my_custom_field",
    "field_type": "Single Line",
    "constraints": [
      { "constraint_name": "max_length", "constraint_value": "255" },
      { "constraint_name": "min_length", "constraint_value": "0" }
    ],
    "allowed_values": [
      { "value": "Option A" },
      { "value": "Option B" }
    ],
    "sub_module": { "internal_name": "request" }
  }
}
```

---

### 7. Create UDF Field

- **URL:** `{INSTANCE_URL}/api/v3/udf_fields`
- **Method:** `POST`
- **Request Body:** (form-encoded under `input_data`)
```json
{
  "udf_field": {
    "name": "my_custom_field",
    "display_name": "My Custom Field",
    "field_key": "txt_my_custom_field",
    "field_type": "Single Line",
    "sub_module": { "internal_name": "request" },
    "constraints": [
      { "constraint_name": "min_length", "constraint_value": "0" },
      { "constraint_name": "max_length", "constraint_value": "255" }
    ],
    "allowed_values": [
      { "value": "Option A" },
      { "value": "Option B" }
    ]
  }
}
```
- **Response Body:**
```json
{
  "udf_field": {
    "id": "90000000099999",
    "name": "my_custom_field",
    "display_name": "My Custom Field",
    "field_key": "txt_my_custom_field",
    "field_type": "Single Line"
  }
}
```

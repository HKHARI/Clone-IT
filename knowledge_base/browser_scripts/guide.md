# SDP Browser Scripts — Technical Artifact

> **Purpose**: Single-point reference for AI tools and developers to generate or extend browser-run scripts for ServiceDesk Plus On-Demand (SDP). Given a **use case** and optional **URL/portal** details, a script can be produced that runs inside an SDP instance in the browser.
>
> **Last updated**: 2026-02-24  
> **Keep this file in sync when adding new patterns or globals.**

---

## 1. Overview

### 1.1 What This Covers

- Scripts that run **inside the browser** while the user is logged into an SDP instance (same-origin).
- **Org-specific**: All operations stay within the same organization. Portal id (app id / instance id) is used to target **another instance in the same org** when the script runs on one instance and needs to read from or write to another.
- **No cross-origin**: Scripts are pasted in the DevTools console of an SDP tab; no separate runner page or token-based cross-origin calls.

### 1.2 When to Use This Artifact

- You need a **new use case** (e.g. bulk delete UDFs, copy entities from one portal to another, run a one-off admin task).
- You will provide: **use case description** and, if needed, **portal/app id** or **module** (e.g. request, problem, change).
- The artifact is used to **generate a working script** that follows SDP’s in-page API and conventions.

---

## 2. Runtime Context

| Aspect | Detail |
|--------|--------|
| **Where script runs** | Browser console (DevTools → Console) on a tab where the user is logged into an SDP instance. |
| **Origin** | Same as the SDP instance (e.g. `https://your-instance.sdpondemand.manageengine.com`). |
| **Auth** | Session cookie (user is already logged in). No OAuth or API token in the script. |
| **CSRF** | Required for state-changing requests. Use page globals when available (see §4). |

### 2.1 Portal Id (App Id / Instance Id)

- **Portal**, **app id**, and **instance id** refer to the **same** identifier for an SDP instance in the org.
- **Current page** = the instance whose URL is open in the tab. API calls with **no** portal targeting go to this instance.
- **Another instance in the same org** = target by sending the header **`x-sdpod-appid`** with that instance’s portal id. Used for “run on instance A, read/write data for instance B” (e.g. migrate from source portal to current).

**Typical flow (cross-portal):**

- User opens the **destination** instance in the browser and runs the script.
- Script asks for **source portal id** (e.g. `prompt("Enter the source instance id/app id")`).
- **GET** requests that fetch from the source use `headers: { 'x-sdpod-appid': portalId }`.
- **POST** (or other write) requests that create/update on the **current** instance are made **without** that header (so they apply to the open instance).

**Single-instance scripts** (e.g. “delete all UDFs on current instance”) do not need a second portal id; the script only uses the current page context.

---

## 3. URL and Path Conventions

### 3.1 Relative Paths

- Scripts use **relative** paths, so they work on any SDP instance domain.
- Examples: `/solutions`, `/api/v3/requests/_metainfo`, `/api/v3/udf_fields/123`.

### 3.2 Asset or Cross-Portal URLs

- When loading **resources from another portal** in the same org (e.g. attachment URL from source), use:
  - **Path form**: `/app/{portalId}/api/v3{path}`
  - Example: `/app/` + portalId + `/api/v3` + attachmentPath

---

## 4. Globals and Helpers (In-Page)

These are available on the SDP page when the script runs. Use them when present; otherwise fall back to `fetch` with the same headers.

| Global / Helper | Purpose |
|-----------------|--------|
| **jQuery** | DOM and AJAX; often used as `jQuery.sdpapi` or for `loadAjaxURL`. |
| **jQuery.sdpapi.get** | GET request with SDP defaults. |
| **jQuery.sdpapi.post** | POST request with SDP defaults. |
| **getAsInputData(obj)** | Wraps `obj` into the request body format the API expects (e.g. form-encoded `input_data` with JSON). Use for `data` in `sdpapi.get`/`sdpapi.post`. |
| **loadAjaxURL(options)** | Raw AJAX (e.g. file upload). Options: `type`, `url`, `data`, `contentType`, `processData`, `headers`, `success`, `error`. |
| **csrfParamName** | CSRF parameter name (page may set this). |
| **csrfParamValue** | CSRF token value. |
| **sdpEach** | Utility to iterate (e.g. over keys). |
| **uploadImageURI** | May exist for inline image upload (reference: solutions script). |

**CSRF header** (when making raw `fetch` or custom AJAX):

- If `typeof csrfParamName !== 'undefined' && typeof csrfParamValue !== 'undefined'`:
  - Add header: `'X-ZCSRF-TOKEN': csrfParamName + '=' + csrfParamValue`

**Accept header** (use one consistently per API area):

- `application/vnd.manageengine.sdp.v3+json` (SDP v3)
- Or `application/vnd.manageengine.v3+json` (generic v3) where the product uses it.

---

## 5. API Call Patterns

### 5.1 GET (list or get one)

**Using jQuery.sdpapi.get (when available):**

```javascript
jQuery.sdpapi.get({
  url: "/solutions",   // or "/api/v3/requests/_metainfo", etc.
  headers: { 'x-sdpod-appid': portalId },  // omit for current instance
  data: getAsInputData({ list_info: { start_index: 1, row_count: 100, get_total_count: true } }),
  callback: function (response, issuccess) {
    if (issuccess) {
      // use response
    }
  }
});
```

**Using fetch (e.g. for metainfo, or when sdpapi is not needed):**

```javascript
fetch('/api/v3/requests/_metainfo', {
  method: 'GET',
  credentials: 'same-origin',
  headers: {
    'Accept': 'application/vnd.manageengine.sdp.v3+json',
    'X-ZCSRF-TOKEN': (typeof csrfParamName !== 'undefined' && typeof csrfParamValue !== 'undefined')
      ? (csrfParamName + '=' + csrfParamValue) : ''
  }
})
  .then(function (res) { return res.json(); })
  .then(function (data) { /* use data */ })
  .catch(function (err) { console.error(err); });
```

### 5.2 POST (create / update)

**Using jQuery.sdpapi.post:**

```javascript
jQuery.sdpapi.post({
  url: "/solutions",   // or appropriate endpoint
  data: getAsInputData(payloadObject),
  callback: function (response, issuccess) {
    if (issuccess) {
      // use response
    }
  }
});
```

- POST without `x-sdpod-appid` targets the **current** (open) instance.

### 5.3 DELETE (or other methods)

- Use **fetch** with `method: 'DELETE'` (or PUT/PATCH as needed), same `credentials` and headers (Accept + CSRF) as above.
- Example: `fetch('/api/v3/udf_fields/' + id, { method: 'DELETE', credentials: 'same-origin', headers: { ... } })`.

### 5.4 File upload (multipart)

- Use **loadAjaxURL** with `FormData`, `contentType: false`, `processData: false`, and headers including Accept and X-ZCSRF-TOKEN (see reference scripts).

---

## 6. Script Structure (Template for Any Use Case)

Use this as a checklist when generating a script:

1. **Config / inputs**
   - Portal id (if cross-portal): e.g. `var portalId = prompt("Enter the source instance id/app id");` or a constant.
   - Module or entity (e.g. `request`, `problem`, `change`, `solutions`) if the use case is entity-specific.
   - Any other parameters (e.g. row count, confirm before destructive action).

2. **Entry**
   - Single run on paste (IIFE) or one main function called at the end.
   - Optional `confirm()` before destructive or large operations.

3. **Helpers**
   - CSRF + Accept headers (function or inline).
   - Optional: `getAsInputData` usage or manual `input_data` encoding for POST.

4. **Flow**
   - **List/get** from the right endpoint (current or with `x-sdpod-appid`).
   - **Process** (filter, transform, validate).
   - **Write** (POST/PUT/DELETE) to the correct instance (current = no header; other = header if supported).

5. **Progress and errors**
   - `console.log` / `console.warn` for progress and summary.
   - Collect failed items (e.g. ids or names) and log or show at the end.
   - For long runs: sequential calls (e.g. process next index after callback) to avoid rate limits; optional delay (e.g. `setTimeout`) if the API throttles.

6. **No hardcoded domain**
   - Use relative URLs only so the script works on any instance.

---

## 7. Use Case → Script Generation (For AI)

When asked to **generate a browser script for SDP**:

1. **Use this artifact** as the single source of truth for:
   - Runtime context (same-origin, session, portal id meaning).
   - Globals and CSRF/Accept headers.
   - API patterns (sdpapi.get/post, getAsInputData, fetch for DELETE/custom).
   - URL rules (relative paths; `/app/{portalId}/api/v3...` for cross-portal assets).

2. **From the use case**, determine:
   - **Scope**: Single instance (current page only) vs. cross-portal (source portal id → current instance).
   - **Entities**: Which API paths (e.g. `/solutions`, `/api/v3/requests/_metainfo`, `/api/v3/udf_fields`).
   - **Actions**: List, get one, create, update, delete.
   - **Confirmation**: Whether to `confirm()` before destructive or bulk operations.
   - **Rate limiting**: Sequential processing and optional delays if the use case is bulk.

3. **Output** a single, self-contained script that:
   - States the use case in a short comment at the top.
   - Sets config (portal id and/or module) at the top or via one prompt.
   - Uses the correct pattern (sdpapi vs fetch) and headers.
   - Handles success and failure and reports a short summary (e.g. “Done. Deleted: N, Failed: M” or “Migrated: N”).

4. **Do not** rely on endpoints or request bodies that are not described in this artifact or in the project’s `artifacts/endpoints.md`; if the use case needs a specific endpoint, refer to that doc or ask for the exact path and method.

---

## 8. Reference Scripts (Examples Only)

- **`examples/migrate_solution.js`**  
  Cross-portal: runs on destination instance; user supplies **source** portal id. Lists solutions from source (GET with `x-sdpod-appid`), fetches each, then POSTs to current (no header). Uses `jQuery.sdpapi.get/post`, `getAsInputData`, `loadAjaxURL`, and `/app/{portalId}/api/v3...` for attachment URLs.

- **`examples/remove_all_udfs.js`**  
  Single-instance: runs on current instance. GETs metainfo from `/api/v3/{module}s/_metainfo`, then DELETE per UDF. Uses `fetch`, CSRF helper, and `confirm()` before delete. Config: `MODULE_TO_CLEAN` (e.g. `request`, `problem`, `change`).

These illustrate the patterns above; the artifact itself is **general** and not tied to solutions or UDFs.

---

## 9. Quick Reference

| Need | Use |
|------|-----|
| Portal id = app id = instance id | Same concept; use for `x-sdpod-appid` when targeting another instance in the org. |
| Current instance | No `x-sdpod-appid`; relative URLs. |
| GET with SDP encoding | `jQuery.sdpapi.get` + `getAsInputData` + optional `headers`. |
| POST with SDP encoding | `jQuery.sdpapi.post` + `getAsInputData`. |
| DELETE or custom method | `fetch` with `credentials: 'same-origin'`, Accept + CSRF headers. |
| CSRF | `X-ZCSRF-TOKEN: csrfParamName + '=' + csrfParamValue` (guard with typeof checks). |
| Resource from another portal | Path: `/app/` + portalId + `/api/v3` + path. |
| User confirmation | `confirm("Message")` before destructive or bulk actions. |
| Sequential bulk work | Call next step in callback/finally; optional `setTimeout` for rate limit. |

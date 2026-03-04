# Knowledge Base

> Central reference for all project documentation and technical guides.

## Migration Tool

The Python CLI + Web UI wizard for migrating SDP On-Demand configuration.

| Doc | Description |
|-----|-------------|
| [overview.md](migration/overview.md) | **Start here** — architecture, three-layer design, registry config, extension guide |
| [auth.md](migration/auth.md) | Authentication module — token management, grant code exchange, validation |
| [udf_migration.md](migration/udf_migration.md) | UDF migration — fetch, compare, transform, create, summarize |
| [template_migration.md](migration/template_migration.md) | Template migration — selection, UDF dependency resolution, payload trimming |
| [decisions/](migration/decisions/) | Architecture decision records (e.g. UI approach analysis) |

## API Reference

| Doc | Description |
|-----|-------------|
| [endpoints.md](api/endpoints.md) | SDP On-Demand v3 API — request/response examples for all endpoints used |

## Browser Scripts

In-browser console scripts for SDP admin tasks (separate from the migration tool).

| Doc | Description |
|-----|-------------|
| [guide.md](browser_scripts/guide.md) | Script conventions, API patterns, CSRF handling, generation template |
| [examples/](browser_scripts/examples/) | Reference scripts (migrate solutions, remove UDFs, Deluge) |

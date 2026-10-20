# AsiliLedger

A blockchain-based timber traceability web application for the forestry supply chain in Kenya.

AsiliLedger records timber batches, their origins, and custody events across forestry operations, transport, processing, and sale. It combines authenticated QR-code lookup, role-based access control, MySQL-backed records, and a custom SHA-256 hash-linked ledger.

> Project status: development / academic prototype. Core workflows have been implemented and tested during development. Completion of every feature and resolution of historical ledger mismatches should be confirmed against the current code and test suite before deployment.

## Contents

- [Overview](#overview)
- [Technology stack](#technology-stack)
- [Roles and access](#roles-and-access)
- [Traceability workflow](#traceability-workflow)
- [Ledger design](#ledger-design)
- [Local setup](#local-setup)
- [First administrator and reference data](#first-administrator-and-reference-data)
- [Using the application](#using-the-application)
- [API overview](#api-overview)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Security and limitations](#security-and-limitations)
- [Deployment notes](#deployment-notes)
- [Project maintenance](#project-maintenance)

## Overview

The project supports tracking timber from its recorded source plot through custody changes. Each authorized operation creates a transaction that can be anchored into the application ledger.

Main capabilities developed for the project include:

- Administrator-managed users and organization assignments.
- Authentication using bcrypt password hashes and JWTs.
- Timber-batch registration with species, quantities, harvest dates, source plots, and permits.
- Organization-aware access checks for batches, plots, permits, and vehicles.
- QR-code generation, download, token rotation, and revocation.
- Authenticated batch lookup and role-specific operations.
- Custody events for harvest, loading, unloading, processing, and sale.
- Block-to-transaction membership records and SHA-256 integrity checks.
- Audit logging for application actions.
- A Bootstrap interface with sidebar navigation.

The repository is the source of truth for available endpoints and features. This README reflects the implementation discussed during development, not an independent code audit.

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript, Bootstrap, Jinja templates |
| Database | MySQL-compatible relational database |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Password hashing | bcrypt |
| API authentication | JWT / PyJWT |
| Ledger | Custom Python hash-linked ledger using SHA-256 |
| QR generation | qrcode, Pillow |
| Database administration | phpMyAdmin, optional |

phpMyAdmin is an administration tool, not the database or the Flask runtime. Apache/PHP are needed only if required by your phpMyAdmin installation; Flask runs separately.

## Roles and access

| Role | Intended responsibilities |
| --- | --- |
| Admin | Manage users and reference records; oversee operations; force anchoring where enabled |
| Forestry officer | Register timber batches and source/harvest information within authorized scope |
| Transporter | Record permitted loading and unloading operations |
| Mill | Process timber and record permitted downstream operations |
| Inspector | Review authorized provenance, custody, and ledger information |
| Buyer | View permitted provenance and receipt/sale information |

Role labels and exact permissions must match the current authorization decorators and permission helpers. Some earlier development versions used `logger` instead of `forestry_officer`; do not mix these values without an explicit migration.

Authentication does not automatically authorize access to every batch. The backend must also check organization relationships and the requested action.

## Traceability workflow

```text
Organizations, users, plots, permits, and vehicles
                         |
                         v
Batch registration -> initial harvest transaction -> QR label
                         |
                         v
Loading -> unloading at destination -> processing -> sale
                         |
                         v
Transaction hashes -> block membership -> ledger verification
```

The transaction route shared during development used these state transitions:

| Event | Required batch state | Resulting batch state |
| --- | --- | --- |
| Harvest / batch creation | New batch | harvested |
| load | harvested | in_transit |
| unload | in_transit | at_destination |
| process | at_destination | at_mill |
| sale | at_mill | sold |

The backend additionally validates roles, custody, destination organizations, and vehicles where applicable. A permit belonging to a plot's organization is not automatically proof that it authorizes that specific plot; plot-level authorization requires an explicit relationship and validation rules.

## Ledger design

AsiliLedger uses a custom, centrally operated hash-linked ledger. It is not a cryptocurrency network and does not currently claim decentralized consensus or proof-of-work security.

### Records and membership

- `transactions` stores custody-event data and its transaction hash.
- `blockchain_blocks` stores block number, timestamp, previous hash, aggregate transaction hash, nonce, block hash, and metadata.
- `blockchain_block_transactions` records the membership of transactions in blocks.
- Genesis is block `0` and has no member transactions.
- The shared implementation uses an anchoring threshold of five pending transactions. An authorized force-anchor operation can anchor a smaller backlog.
- The threshold triggers anchoring; it is not a maximum block size. One block may contain more than five pending transactions.

### Current hash format

Transaction hashes are calculated from a JSON payload with sorted keys and compact separators. The current helper includes event identity, actor and organization references, permit/vehicle references, quantities, occurrence time, coordinates, and notes.

The shared block implementation uses:

```text
transactions_hash = SHA256(compact_JSON(sorted(member_transaction_hashes)))
block_hash = SHA256(previous_hash + transactions_hash + string(nonce))
```

In this format, block number and timestamp are not included in `block_hash`. Changing the format requires a deliberate migration/versioning strategy, not silently changing verification rules for existing blocks.

### Persistence considerations

Reload database-stored event values before creating their hash:

```python
db.session.add(tx)
db.session.flush()
db.session.refresh(tx)
tx.transaction_hash = hash_transaction(tx)
db.session.commit()
```

This helps avoid differences between pre-storage Python values and persisted timestamp/numeric representations. Hashed fields must not subsequently change through ordinary updates.

Do not enable `AUTO_INCREMENT` on the logical block number when the application explicitly assigns genesis as `0` and subsequent block numbers. Ensure the model and actual database schema agree.

### Interpreting verification

A successful full-ledger result reports:

- `blocks_checked`: persisted blocks checked, including genesis.
- `transactions_checked`: anchored transaction contents checked.
- `unanchored_transactions`: records still awaiting anchoring.

A valid genesis-only ledger does not certify pending custody events. Verification establishes internal consistency, not the truth of field observations, permit authenticity, or physical identity of timber.

## Local setup

### Prerequisites

- Python compatible with the repository dependencies; development used Python 3.12.
- MySQL-compatible database server.
- Git.
- A modern browser.
- Optional: phpMyAdmin for local database administration.

### 1. Get the project

Clone or download this repository, then open its root directory:

```bash
cd AsiliLedger
```

### 2. Create a virtual environment

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Use the repository requirements rather than dependency versions copied from earlier development examples.

### 4. Create the database and application account

Create a database named `timber_tracker` and a dedicated non-root application user using your database administration tool. Give the account access to the project database only. Use separate migration and runtime privileges where practical.

### 5. Configure the environment

Create `.env` in the location expected by `config.py`:

```dotenv
SECRET_KEY=replace_with_a_generated_random_secret
MYSQL_USER=tt_user
MYSQL_PASSWORD=replace_with_your_database_password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=timber_tracker
```

Generate a secret locally:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Verify these variable names against the current `config.py`. If it constructs a database URL from strings, correctly encode special characters in credentials or use SQLAlchemy's URL builder.

Never commit `.env`. Keep an `.env.example` with placeholder values instead.

### 6. Initialize or migrate the schema

Use the schema-management method actually configured in the repository.

If Flask-Migrate is integrated and an existing migration history is included:

```bash
flask --app app:create_app db upgrade
```

If the prototype still creates tables inside `create_app()` using `db.create_all()`, starting the application may create missing tables. It will not migrate existing columns or constraints. Do not run both initialization approaches blindly against an existing database.

The application should call `initialize_chain()` inside an application context after the ledger tables exist. Startup restores persisted blocks and pending transaction IDs; loading pending IDs alone does not necessarily anchor them.

### 7. Run locally

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

If the repository uses the application factory without a direct entry point:

```bash
flask --app app:create_app run
```

Inspect registered routes with:

```bash
flask --app app:create_app routes
```

## First administrator and reference data

The development bootstrap script was:

```bash
python seeds/admin_seed.py
```

Inspect and update this script before running it. Replace any demonstration email or hard-coded password; do not retain credentials published in example code. Prefer an interactive password prompt or environment-supplied bootstrap credentials, and never print passwords.

Normal user creation should be admin-only. Do not expose public role selection or public administrator registration.

Seed reference data in dependency order:

1. Organizations.
2. Forest plots, permits, and vehicles linked to organizations.
3. Users linked to their organizations.
4. Batches created through the application.
5. Custody events created through the permitted workflow.

Use the seed mechanism included in your repository. Do not assume a generic seed command exists. Sample organizations, permit numbers, vehicles, and locations are fictional development data, not official authorizations.

## Using the application

1. Sign in using an authorized account.
2. Open New Batch as an admin or forestry officer.
3. Select species, enter quantities and harvest date, and choose an authorized plot.
4. Select a matching valid harvest permit. Where dependent dropdowns are implemented, changing the plot clears and filters the permit selection.
5. Submit once and retain the generated QR label.
6. Use authenticated tracking/scanning to resolve a batch.
7. Record only the next permitted custody event for your role and organization.
8. Review the batch timeline and block anchors on the blockchain page.
9. Verify the full ledger using an authorized account.

QR codes identify records; they do not independently grant access or prove legality. There is no intended public tracking view. A protected lookup still requires login and batch-level authorization.

For phone testing, `127.0.0.1` refers to the phone itself, not the development computer. Configure a reachable application base URL and appropriate HTTPS before printing labels for a shared environment.

## API overview

These routes appeared in the development implementation. Check the current route inventory for final permissions and availability.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/login` | Authenticate and obtain a JWT |
| POST | `/api/register` | Admin-managed user creation |
| GET | `/api/me` | Current user details |
| GET | `/api/forest-plots` | Authorized plot options |
| GET | `/api/permits?type=harvest` | Authorized permit options |
| GET / POST | `/api/batches` | List or create batches |
| GET | `/api/batches/by-tag/<tag>` | Authorized batch lookup |
| GET | `/api/batches/<id>/qr` | Authorized QR image response |
| GET | `/api/batches/<id>/qr-data` | Authorized QR image data |
| GET | `/api/batches/<id>/qr/download` | Download QR image |
| POST | `/api/batches/<id>/qr/rotate` | Issue a replacement QR token |
| POST | `/api/batches/<id>/qr/revoke` | Revoke the QR token |
| GET / POST | `/api/transactions` | List or record custody events |
| GET | `/api/transactions/<id>` | Authorized event details |
| GET | `/api/blockchain/verify` | Verify persisted ledger integrity |
| POST | `/api/blockchain/anchor` | Admin force-anchor operation |

Authenticated API requests use:

```http
Authorization: Bearer <token>
```

Do not share tokens in screenshots, support messages, commits, or logs.

Expected status conventions include `200` success, `201` creation, `400` validation failure, `401` missing/invalid authentication, `403` denied permission, `404` unavailable record, and `409` duplicate/conflicting data or failed ledger integrity where implemented.

The historical `/api/batches/<id>/verify` implementation returned `verified: true` while listing data without cryptographic checks. Do not present that field as proof of integrity unless the endpoint has since been replaced with actual verification.

## Testing

Run the repository's configured test suite. If it uses pytest:

```bash
pytest -q
```

Use a dedicated test database, not a production or important development database. Seed isolated fixtures and clean them up safely.

Minimum acceptance checks:

- Valid and invalid login; expired/modified JWT handling.
- Admin-only user registration and role assignment.
- Cross-organization denial for batch, plot, permit, and vehicle IDs.
- Batch creation rejects duplicate tags, invalid quantities, future dates, and mismatched permits.
- Harvest creation produces exactly one event and a reproducible stored hash.
- Unauthorized QR access fails; revoked tokens do not resolve.
- Invalid state transitions are rejected.
- Batch and event changes are committed consistently.
- Pending events anchor successfully, with membership records.
- Ledger verification still succeeds after application restart.
- Controlled transaction/block tampering is detected in a disposable database.
- Backup restoration is tested.

Record test results and known failures rather than assuming every feature is complete because the interface appears to work.

## Troubleshooting

### Foreign-key errors during batch creation

Select existing plots and permits from reference-data options. Ensure the selected permit belongs to the selected plot's organization and the user is authorized to use both.

### `undefined` verification counts

The frontend and backend response formats disagree. The frontend expects `blocks_checked`, `transactions_checked`, and `unanchored_transactions`. Keep only one GET handler for `/api/blockchain/verify`.

### Unexpected genesis number

Inspect the real schema and database records. A genesis intended as `0` may have been stored as `1` because of auto-increment handling. Do not renumber anchored blocks or delete memberships blindly; back up and follow an explicit repair plan.

### Transaction data does not match its stored hash

Do not overwrite historical hashes just to produce a green result. Inspect the original hashing code, numeric/time representations, and later mutations. Refresh stored values before hashing new records and test a genuinely new batch. Existing mismatches require a documented investigation or an explicitly approved rebuild of disposable test data.

### SQL entered into the Python shell

Run SQL statements in a SQL client or phpMyAdmin. The `>>>` prompt expects Python. Flask shell commands can query models with SQLAlchemy instead.

## Security and limitations

Before any shared deployment, review these implementation-specific issues:

- Local storage and local hosting do not automatically make data secure. Enforce authentication, authorization, backups, and restricted database access.
- JWTs in browser localStorage are exposed to successful same-origin script injection. Review token/session design, output encoding, expiry, and logout/revocation behavior.
- The shared QR implementation writes images under `static/qr_codes` using predictable batch-based filenames. Static files can bypass protected API handlers. Move QR artifacts to private storage and serve them only through authorized routes before claiming private QR downloads.
- Storing a QR image/base64 containing a raw token means the token can be recovered from that image. A hashed token column does not mean the database contains no recoverable token material.
- QR rotation/revocation does not prevent physical copying of a label; it changes whether the token resolves.
- A GET QR route that silently issues a replacement token when a file is missing can invalidate printed labels. Prefer explicit authorized replacement rather than token rotation as a side effect of viewing.
- The current in-memory chain and pending list require additional database locking/coordination for concurrent workers. Do not assume multi-worker safety.
- Keep block writes, membership writes, and anchoring timestamps in one database transaction. Handle flush and commit failures with rollback and in-memory cleanup.
- A post-commit anchoring failure must not be represented as if batch creation rolled back. Keep committed events pending and return/log a clear anchoring status to avoid duplicate retries.
- A privileged operator controlling the whole database can potentially rewrite records and hashes. Independent checkpoints or validators are needed for stronger tamper resistance.
- The system does not establish legal compliance or physical timber authenticity solely through QR codes or hashes. Field verification and valid regulatory evidence remain necessary.

Historical transaction-hash mismatches were encountered during development. Verify their resolution against the current database and test results; this README does not claim they have been repaired.

## Deployment notes

For a shared evaluation or production-like environment:

- Use a production WSGI server appropriate to the platform, not Flask's development server.
- Disable debug mode and do not expose tracebacks or SQL errors.
- Use HTTPS and a configured trusted public base URL for QR generation.
- Keep MySQL and phpMyAdmin off the public internet.
- Use dedicated database credentials and least privilege.
- Store secrets outside version control.
- Use migrations and back up before schema changes.
- Restrict and validate uploads if document evidence is implemented.
- Add login and expensive-operation rate limits.
- Protect logs and avoid logging passwords, JWTs, and raw QR tokens.
- Configure tested backups, restore procedures, and monitoring.
- Resolve concurrent anchoring before using multiple application workers.

A local academic demonstration can remain local; cloud hosting is not required to demonstrate the project's workflows.

## Project maintenance

Before submission or handover:

- Confirm this README matches the final routes, roles, and seed commands.
- Include `.env.example`, dependency requirements, and migration history.
- Update the ERD and role-permission matrix.
- Include test instructions, measured results, and known limitations.
- Prepare a fictional-data demo from harvest through sale and ledger verification.
- Add author/institution details if required for assessment.
- Add a `LICENSE` file only after selecting an appropriate license. No license is assumed by this README.

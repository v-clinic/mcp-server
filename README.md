# vClinic MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes a virtual clinic's clinical data and knowledge base as tools for AI agents. Agents can manage patients, visits, diagnoses, treatments, lab orders, radiology orders, and search both external medical literature and an internal RAG knowledge base.

---

## Features

| Category | Tools |
|---|---|
| **Patients** | `create_patient`, `get_patient`, `search_patients` |
| **Visits** | `create_visit`, `get_visit`, `get_visits_for_patient`, `update_visit` |
| **Diagnoses** | `create_diagnosis`, `update_diagnosis`, `get_diagnoses_for_visit` |
| **Treatments** | `create_treatment`, `update_treatment`, `get_treatments_for_visit` |
| **Lab** | `create_lab_order`, `get_lab_order`, `get_pending_lab_orders`, `update_lab_order_status`, `create_lab_result`, `get_lab_results`, `update_lab_result` |
| **Radiology** | `create_radiology_order`, `get_radiology_order`, `get_pending_radiology_orders`, `update_radiology_order_status`, `create_radiology_report`, `get_radiology_report`, `update_radiology_report` |
| **Knowledge search** | `search_pubmed`, `get_clinical_guidelines`, `search_clinic_knowledge` |
| **Staff** | `seed_staff` |

All tool calls are audit-logged to `data/audit.log` (HIPAA § 164.312(b)).

---

## Project Structure

```
vClinic-mcp-server/
├── server.py               # MCP server entry point
├── audit_logger.py         # HIPAA audit log decorator
├── sample_client.py        # Test client using langchain-mcp-adapters
├── requirements.txt
├── backend/
│   ├── db.py               # SQLite connection & init
│   └── schema.sql          # Synthea-aligned schema + operational tables
├── tools/
│   ├── patient_tools.py
│   ├── visit_tools.py
│   ├── diagnosis_tools.py
│   ├── treatment_tools.py
│   ├── lab_tools.py
│   ├── radiology_tools.py
│   ├── medical_search_tools.py
│   └── ...
├── rag_tools/
│   └── rag_tools.py        # Pinecone RAG — indexes knowledge_base/
├── knowledge_base/
│   ├── drug_formulary.md
│   ├── clinical_protocols.md
│   └── clinic_sops.md
└── data/
    ├── vclinic.db          # SQLite database (created on first run)
    └── audit.log           # Append-only CSV audit trail
```

---

## Requirements

- Python 3.11+
- [Pinecone local dev server](https://docs.pinecone.io/guides/operations/local-development) running on `http://localhost:5080`
- OpenAI API key (for `text-embedding-3-small` embeddings and agent LLM calls)

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your OpenAI API key
export OPENAI_API_KEY=sk-...
```

---

## Running the Server

```bash
# Normal start — creates the DB on first run, loads the Pinecone index
python -m server

# Wipe and recreate the database (drops all patient data)
python -m server --reinit
```

On startup the server will:
1. Create `data/vclinic.db` and seed default staff (first run only, or with `--reinit`).
2. Build or load the Pinecone knowledge-base index (`vclinic-knowledge`).

---

## Running the Sample Client

The sample client connects to the server over stdio and lists all registered tools:

```bash
python sample_client.py

# Start the server with a fresh database
VCLINIC_REINIT=1 python sample_client.py
```

---

## Knowledge Base (RAG)

Internal clinic documents in `knowledge_base/` are indexed into Pinecone at server startup:

| File | Content |
|---|---|
| `drug_formulary.md` | Approved medications, dosing, formulary tiers, contraindications |
| `clinical_protocols.md` | CAP, AGE, HTN, T2DM, fever treatment protocols |
| `clinic_sops.md` | Registration, vitals, lab/radiology ordering, discharge SOPs |

The `search_clinic_knowledge` tool performs semantic search over these documents. If the Pinecone index already exists and contains vectors it is reused; otherwise it is built from scratch (requires an active OpenAI API key).

To force a re-index, delete the Pinecone index and restart the server.

---

## Audit Logging

Every tool call is appended to `data/audit.log` as a CSV row containing:

| Field | Description |
|---|---|
| `event_id` | UUID per call |
| `timestamp` | UTC ISO-8601 |
| `tool` | Tool function name |
| `args` | JSON-encoded arguments |
| `outcome` | `SUCCESS` or `ERROR` |
| `detail` | Error message (if any) |

---

## VS Code / Claude Desktop Configuration

```json
{
  "mcpServers": {
    "vclinic": {
      "command": "python",
      "args": ["-m", "server"],
      "cwd": "/path/to/vClinic-mcp-server",
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```
## ⚠️ License & Disclaimer

This project is a **Proof of Concept (POC)** and is intended solely for **demonstration and educational purposes**.

* **No Liability:** The code owner accepts no responsibility for any damages, data loss, or issues caused by running this software.
* **As-Is:** This software is provided *as-is*, without warranty of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, or non-infringement.
* **Not for Clinical Use:** This system **must not** be used to inform, support, or replace real clinical decisions, diagnoses, or patient care of any kind. All data used is fully synthetic and has no connection to real patients or medical records.
* **License:** Distributed under the MIT License.
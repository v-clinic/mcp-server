-- vClinic Database Schema
-- Table names = CSV filenames; CSV-derived column names match the CSV header exactly (exact case).
-- Tables whose CSV has no primary key column receive an added "Id TEXT PRIMARY KEY".
-- Operational extensions (workflow state, clinical notes) use lowercase names.

PRAGMA foreign_keys = ON;

-- ============================================================
-- Synthea-aligned tables (one per CSV file, exact CSV column case)
-- ============================================================

CREATE TABLE IF NOT EXISTS patients (
    Id                  TEXT PRIMARY KEY,   -- CSV header
    BIRTHDATE           TEXT,
    DEATHDATE           TEXT,
    SSN                 TEXT,
    DRIVERS             TEXT,
    PASSPORT            TEXT,
    PREFIX              TEXT,
    FIRST               TEXT NOT NULL,
    MIDDLE              TEXT,
    LAST                TEXT NOT NULL,
    SUFFIX              TEXT,
    MAIDEN              TEXT,
    MARITAL             TEXT,
    RACE                TEXT,
    ETHNICITY           TEXT,
    GENDER              TEXT,
    BIRTHPLACE          TEXT,
    ADDRESS             TEXT,
    CITY                TEXT,
    STATE               TEXT,
    COUNTY              TEXT,
    FIPS                TEXT,
    ZIP                 TEXT,
    LAT                 REAL,
    LON                 REAL,
    HEALTHCARE_EXPENSES REAL,
    HEALTHCARE_COVERAGE REAL,
    INCOME              REAL
);

CREATE TABLE IF NOT EXISTS organizations (
    Id          TEXT PRIMARY KEY,   -- CSV header
    NAME        TEXT,
    ADDRESS     TEXT,
    CITY        TEXT,
    STATE       TEXT,
    ZIP         TEXT,
    LAT         REAL,
    LON         REAL,
    PHONE       TEXT,
    REVENUE     REAL,
    UTILIZATION INTEGER
);

CREATE TABLE IF NOT EXISTS providers (
    Id           TEXT PRIMARY KEY,   -- CSV header
    ORGANIZATION TEXT REFERENCES organizations(Id),
    NAME         TEXT,
    GENDER       TEXT,
    SPECIALITY   TEXT,
    ADDRESS      TEXT,
    CITY         TEXT,
    STATE        TEXT,
    ZIP          TEXT,
    LAT          REAL,
    LON          REAL,
    ENCOUNTERS   INTEGER,
    PROCEDURES   INTEGER
);

CREATE TABLE IF NOT EXISTS encounters (
    Id                  TEXT PRIMARY KEY,   -- CSV header
    START               TEXT,
    STOP                TEXT,
    PATIENT             TEXT REFERENCES patients(Id),
    ORGANIZATION        TEXT,
    PROVIDER            TEXT,
    PAYER               TEXT,
    ENCOUNTERCLASS      TEXT,
    CODE                TEXT,
    DESCRIPTION         TEXT,
    BASE_ENCOUNTER_COST REAL,
    TOTAL_CLAIM_COST    REAL,
    PAYER_COVERAGE      REAL,
    REASONCODE          TEXT,
    REASONDESCRIPTION   TEXT,
    -- Operational columns (not in CSV)
    status              TEXT NOT NULL DEFAULT 'open',
    chief_complaint     TEXT,
    symptoms            TEXT,
    vital_signs         TEXT,
    medical_history     TEXT,
    notes               TEXT,
    ordering_doctor_id  TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS conditions (
    Id             TEXT PRIMARY KEY,   -- added (not in CSV)
    START          TEXT,
    STOP           TEXT,
    PATIENT        TEXT REFERENCES patients(Id),
    ENCOUNTER      TEXT REFERENCES encounters(Id),
    SYSTEM         TEXT,
    CODE           TEXT,
    DESCRIPTION    TEXT NOT NULL,
    -- Operational columns
    severity       TEXT,
    is_preliminary INTEGER NOT NULL DEFAULT 1,
    doctor_id      TEXT,
    created_at     TEXT,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS allergies (
    Id           TEXT PRIMARY KEY,   -- added (not in CSV)
    START        TEXT,
    STOP         TEXT,
    PATIENT      TEXT REFERENCES patients(Id),
    ENCOUNTER    TEXT REFERENCES encounters(Id),
    CODE         TEXT,
    SYSTEM       TEXT,
    DESCRIPTION  TEXT,
    TYPE         TEXT,
    CATEGORY     TEXT,
    REACTION1    TEXT,
    DESCRIPTION1 TEXT,
    SEVERITY1    TEXT,
    REACTION2    TEXT,
    DESCRIPTION2 TEXT,
    SEVERITY2    TEXT
);

CREATE TABLE IF NOT EXISTS medications (
    Id                TEXT PRIMARY KEY,   -- added (not in CSV)
    START             TEXT,
    STOP              TEXT,
    PATIENT           TEXT REFERENCES patients(Id),
    PAYER             TEXT,
    ENCOUNTER         TEXT REFERENCES encounters(Id),
    CODE              TEXT,
    DESCRIPTION       TEXT,
    BASE_COST         REAL,
    PAYER_COVERAGE    REAL,
    DISPENSES         INTEGER,
    TOTALCOST         REAL,
    REASONCODE        TEXT,
    REASONDESCRIPTION TEXT,
    -- Operational columns
    treatment_type    TEXT,
    dosage            TEXT,
    frequency         TEXT,
    duration          TEXT,
    instructions      TEXT,
    doctor_id         TEXT,
    created_at        TEXT,
    updated_at        TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    Id             TEXT PRIMARY KEY,   -- added (not in CSV)
    DATE           TEXT,
    PATIENT        TEXT REFERENCES patients(Id),
    ENCOUNTER      TEXT REFERENCES encounters(Id),
    CATEGORY       TEXT,
    CODE           TEXT,
    DESCRIPTION    TEXT,
    VALUE          TEXT,
    UNITS          TEXT,
    TYPE           TEXT,
    -- Operational columns
    order_id       TEXT,
    performed_by   TEXT,
    interpretation TEXT,
    notes          TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS procedures (
    Id                TEXT PRIMARY KEY,   -- added (not in CSV)
    START             TEXT,
    STOP              TEXT,
    PATIENT           TEXT REFERENCES patients(Id),
    ENCOUNTER         TEXT REFERENCES encounters(Id),
    SYSTEM            TEXT,
    CODE              TEXT,
    DESCRIPTION       TEXT,
    BASE_COST         REAL,
    REASONCODE        TEXT,
    REASONDESCRIPTION TEXT
);

CREATE TABLE IF NOT EXISTS immunizations (
    Id          TEXT PRIMARY KEY,   -- added (not in CSV)
    DATE        TEXT,
    PATIENT     TEXT REFERENCES patients(Id),
    ENCOUNTER   TEXT REFERENCES encounters(Id),
    CODE        TEXT,
    DESCRIPTION TEXT,
    BASE_COST   REAL
);

CREATE TABLE IF NOT EXISTS imaging_studies (
    Id                   TEXT PRIMARY KEY,   -- CSV header
    DATE                 TEXT,
    PATIENT              TEXT REFERENCES patients(Id),
    ENCOUNTER            TEXT REFERENCES encounters(Id),
    SERIES_UID           TEXT,
    BODYSITE_CODE        TEXT,
    BODYSITE_DESCRIPTION TEXT,
    MODALITY_CODE        TEXT,
    MODALITY_DESCRIPTION TEXT,
    INSTANCE_UID         TEXT,
    SOP_CODE             TEXT,
    SOP_DESCRIPTION      TEXT,
    PROCEDURE_CODE       TEXT,
    -- Operational columns
    order_id             TEXT,
    radiologist_id       TEXT,
    findings             TEXT,
    impression           TEXT,
    recommendations      TEXT,
    is_critical          INTEGER NOT NULL DEFAULT 0,
    performed_at         TEXT,
    updated_at           TEXT
);

CREATE TABLE IF NOT EXISTS careplans (
    Id                TEXT PRIMARY KEY,   -- CSV header
    START             TEXT,
    STOP              TEXT,
    PATIENT           TEXT REFERENCES patients(Id),
    ENCOUNTER         TEXT REFERENCES encounters(Id),
    CODE              TEXT,
    DESCRIPTION       TEXT,
    REASONCODE        TEXT,
    REASONDESCRIPTION TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    Id          TEXT PRIMARY KEY,   -- added (not in CSV)
    START       TEXT,
    STOP        TEXT,
    PATIENT     TEXT REFERENCES patients(Id),
    ENCOUNTER   TEXT REFERENCES encounters(Id),
    CODE        TEXT,
    DESCRIPTION TEXT,
    UDI         TEXT
);

CREATE TABLE IF NOT EXISTS supplies (
    Id          TEXT PRIMARY KEY,   -- added (not in CSV)
    DATE        TEXT,
    PATIENT     TEXT REFERENCES patients(Id),
    ENCOUNTER   TEXT REFERENCES encounters(Id),
    CODE        TEXT,
    DESCRIPTION TEXT,
    QUANTITY    INTEGER
);

-- ============================================================
-- Operational tables (vClinic workflow, not in Synthea CSVs)
-- ============================================================

CREATE TABLE IF NOT EXISTS staff (
    staff_id    TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    role        TEXT NOT NULL,
    department  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_orders (
    order_id            TEXT PRIMARY KEY,
    encounter           TEXT NOT NULL REFERENCES encounters(Id),
    patient             TEXT NOT NULL REFERENCES patients(Id),
    ordering_doctor_id  TEXT NOT NULL REFERENCES staff(staff_id),
    test_name           TEXT NOT NULL,
    test_code           TEXT,
    clinical_notes      TEXT,
    priority            TEXT NOT NULL DEFAULT 'routine',
    status              TEXT NOT NULL DEFAULT 'pending',
    ordered_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS radiology_orders (
    order_id            TEXT PRIMARY KEY,
    encounter           TEXT NOT NULL REFERENCES encounters(Id),
    patient             TEXT NOT NULL REFERENCES patients(Id),
    ordering_doctor_id  TEXT NOT NULL REFERENCES staff(staff_id),
    study_type          TEXT NOT NULL,
    body_part           TEXT NOT NULL,
    clinical_indication TEXT,
    priority            TEXT NOT NULL DEFAULT 'routine',
    status              TEXT NOT NULL DEFAULT 'pending',
    ordered_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

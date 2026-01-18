# CareShift
CareShift is a backend decision-support system that generates a dynamic, acuity-aware nursing shift schedule from simulated electronic health record (EHR) data. The system ingests patient orders, medications, and acuity levels and produces a prioritized, editable timeline for a nurse’s 12-hour shift. The schedule automatically updates when orders change.

This project is designed for educational and demonstration purposes and uses simulated clinical data.

## Motivation
CareShift was inspired by my real-world experience working in pediatric critical care environments where nurses manage complex, time-sensitive workflows under high cognitive load. Many existing systems present data without helping clinicians prioritize tasks across a shift. CareShift explores how backend systems can support safer, more manageable workflows.

## Core Features (Planned)
- Simulated EHR data ingestion (patients, orders, medications)
- Acuity-aware task prioritization
- Dynamic shift timeline generation
- Automatic schedule updates on order changes
- Manual override support
- Robust validation and error handling

## Tech Stack
- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Pytest

## Disclaimer
This project uses simulated data only and is not intended for clinical use.

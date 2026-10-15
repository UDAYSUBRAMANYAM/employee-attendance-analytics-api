# Employee Attendance & Analytics API

A REST API built with FastAPI and MongoDB for employee management, attendance tracking, attendance regularization, and workforce analytics.

## Tech Stack

- **Language:** Python
- **API Framework:** FastAPI
- **Database:** MongoDB
- **Database Driver:** PyMongo
- **Validation:** Pydantic
- **Server:** Uvicorn

## Features

- Employee creation and retrieval.
- Employee filtering, sorting, and pagination.
- Attendance punch-in and punch-out.
- Work-hour, late-arrival, overtime, and half-day calculations.
- Attendance record filtering by date and status.
- Attendance regularization with audit history.
- Employee monthly attendance analytics.
- Department-level attendance summaries.
- Late-arrival leaderboard.
- Department attendance trends.
- Query-plan inspection through explain endpoints.

## Project Structure

```text
candidate_kit/
├── app/
│   ├── __init__.py
│   └── main.py
├── requirements.txt
├── README.md
├── REVIEW.md
├── DECISIONS.md
├── openapi.yaml
├── DATA_MODEL.md
├── PROBLEM_STATEMENT.docx
├── sample_seed.py
└── .gitignore
```

## Prerequisites

- Python 3.11 or a compatible version supported by the dependencies.
- MongoDB 6.0 or newer.
- pip.

## Setup

Run the following commands from the repository root.

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Set the MongoDB connection string and database name.

```powershell
$env:MONGO_URI="mongodb://localhost:27017"
$env:MONGO_DB="attendance_db"
```

For a hosted MongoDB instance, provide its connection URI through `MONGO_URI`.

Do not commit `.env` files, credentials, or other secrets.

### 4. Start the API

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API should be available at:

- API documentation: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/health

## Database and Indexes

The application uses MongoDB collections for employee and attendance data. Indexes are created by the application to support data integrity and query operations.

Refer to `DATA_MODEL.md` for the data model and `DECISIONS.md` for the design rationale.

## API Contract

The supplied `openapi.yaml` describes the API contract and expected behavior.

## Testing

The API can be tested using the supplied assignment test environment and the interactive Swagger documentation at `/docs`.

Run any available tests from the repository root using the test command provided by the assignment or your local test setup.

## Known Limitations

The implementation has not been independently verified against every grader test or against a 100,000-record performance dataset. Concurrency behavior, explain-plan results, and analytics performance should be validated against the target MongoDB environment.

## Configuration and Security

- Configure MongoDB through environment variables.
- Keep credentials and local configuration files out of version control.
- Use a secured MongoDB deployment and appropriate authentication for production.
- Use HTTPS and appropriate access controls before exposing the API publicly.
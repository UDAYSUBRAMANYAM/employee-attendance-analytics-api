"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
from pymongo.errors import DuplicateKeyError
from pydantic import StrictInt
from enum import unique
from fastapi.encoders import isoformat
from pydantic import Field
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pymongo import MongoClient
from datetime import date, time
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI","mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "attendance_db")]

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


from fastapi import Query, HTTPException
# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def compute_late_minutes(punch_in: datetime, shift_start: str,shift_end:str) -> int:
    h, m = map(int, shift_start.split(":"))
    end_h,end_m = map(int,shift_end.split(":"))
    shift_date = punch_in.date()
    if (end_h,end_m) <=(h,m):
        if(punch_in.hour,punch_in.minute) < (end_h,end_m):
            shift_date -= timedelta(days=1)
    start = punch_in.replace(year= shift_date.year,month=shift_date.month,day=shift_date.day,hour=h, minute=m, second=0, microsecond=0)
    elapsed_seconds = (punch_in - start).total_seconds()
    if elapsed_seconds <= 10*60:
        return 0
    return int(elapsed_seconds // 60)

from decimal import Decimal,ROUND_HALF_UP
def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    seconds = (punch_out-punch_in).total_seconds()
    hours = Decimal(str(seconds))/Decimal("3600")
    return float(hours.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))


def compute_overtime(punch_out: datetime,shift_start:str, shift_end: str, date_str: str) -> int:
    start_h,start_m = map(int, shift_start.split(":"))
    end_h, end_m = map(int, shift_end.split(":"))
    end = datetime.fromisoformat(date_str).replace(hour=end_h, minute=end_m,second=0,microsecond=0, tzinfo=IST)
    # start = datetime.fromisoformat(date_str).replace(hour=start_h, minute=start_m,second=0,microsecond=0, tzinfo=IST)
    if(end_h,end_m) <= (start_h,start_m):
        end += timedelta(days=1)
    overtime_seconds = (punch_out - end).total_seconds()
    if overtime_seconds < 30*60:
        return 0
    return int(overtime_seconds // 60)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
from pydantic import BaseModel, Field, model_validator, field_validator

class EmployeeIn(BaseModel):
    emp_code: str = Field(pattern=r"^EMP\d{4,6}$")
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    department: str = Field(min_length=1, max_length=50)
    shift_start: str = Field(
        default="09:30",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    shift_end: str = Field(
        default="18:30",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    joined_on: date

    @field_validator("department")
    @classmethod
    def department_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("department cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_shift_times(self):
        if self.shift_start == self.shift_end:
            raise ValueError("shift timings cannot be the same")
        return self

from typing import Literal,Annotated

class PunchIn(BaseModel):
    emp_code: str
    punched_at: Optional[Annotated[StrictInt,Field(ge=100_000_000_000, le=4_102_444_800_000),]] = None
    status: Literal["PRESENT","WFH","ON_DUTY"] = "PRESENT"

class PunchOut(BaseModel):
    emp_code: str
    punched_at: Optional[Annotated[StrictInt,Field(ge=100_000_000_000, le=4_102_444_800_000),]] = None

from pydantic import BaseModel, Field, StrictInt, ConfigDict
from typing import Literal


class RegularizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)

    status: Literal[
        "PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"
    ] | None = None

    punch_in: StrictInt | None = Field(
        default=None, ge=100_000_000_000,
        le=253_402_300_799_999
    )
    punch_out: StrictInt | None = Field(
        default=None, ge=100_000_000_000,
        le=253_402_300_799_999
    )

# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(503, detail="MongoDB is not available")


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn ):
    if db.employees.find_one({"emp_code": body.emp_code}):
        raise HTTPException(409, "emp_code already exists")
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)
    doc["joined_on"] = body.joined_on.isoformat()
    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "emp_code already exists")
    doc["created_at"] = epoch_ms(doc["created_at"])
    doc.pop("_id",None)
    return doc
    

@app.get("/employees")
def list_employees(department: Optional[str] = None, page: int = Query(1,ge=1), page_size: int = Query(20, ge=1, le=100)):
    q = {}
    if department is not None:
        q["department"] = department
    skip = (page -1) * page_size
    total = db.employees.count_documents(q)
    items = list(db.employees.find(q, {"_id": 0}).sort("emp_code",1).skip(skip).limit(page_size))
    for item in items:
        item["created_at"] = epoch_ms(item["created_at"])
    return {"items": items, "total": total, "page": page, "page_size": page_size}  

db.employees.create_index([("emp_code",1)],unique=True)
db.attendance_logs.create_index([("emp_code", 1), ("date", 1)],unique=True)
db.attendance_logs.create_index([("date", -1), ("emp_code", 1)])

@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if emp is None:
        raise HTTPException(404,"emp_code not found")
    if body.punched_at is not None:
        ts = datetime.fromtimestamp(body.punched_at / 1000,tz=timezone.utc).astimezone(IST)
    else: 
        ts = datetime.now(IST)
    ts = ts.replace(microsecond=0)
    start_h,start_m = map(int,emp["shift_start"].split(":"))
    end_h,end_m = map(int,emp["shift_end"].split(":"))
    attendence_date = ts.date()
    if((end_h,end_m)<=(start_h,start_m)) and (ts.hour,ts.minute)<(end_h,end_m):
        attendence_date -= timedelta(days=1)
    d=attendence_date.isoformat()
    if db.attendance_logs.find_one({"emp_code": body.emp_code, "date": d}):
        raise HTTPException(409, "already punched in for this date")
    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": compute_late_minutes(ts, emp["shift_start"],emp["shift_end"]),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }
    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "already punched in for this date")
    print("Doc",doc)
    print("Doc_id ", type(doc.get("_id")))
    response = {
        **doc,
        "punch_in": int(ts.timestamp() * 1000),
        "punch_out": None,
    }

    response.pop("_id", None)

    return response

@app.post("/attendance/punch-out")
def punch_out(body:PunchOut):
    emp = db.employees.find_one({"emp_code":body.emp_code}) 
    if emp is None:
        raise HTTPException(404,"Employee not found")
    if body.punched_at is not None:
        ts = datetime.fromtimestamp(body.punched_at / 1000,tz=timezone.utc).astimezone(IST)
    else: 
        ts = datetime.now(IST)
    ts = ts.replace(microsecond=0)

    record = db.attendance_logs.find_one({"emp_code":body.emp_code,"punch_out": None,},sort=[("punch_in",-1)])
    if record is None or record["punch_in"] is None:
        raise HTTPException(404,"No active punch-in found for this employee")
    if record["punch_out"] is not None:
        raise HTTPException(409,"Already Punched out")
    punch_in_ist = to_ist(record["punch_in"])
    if body.punched_at is not None:
        duration_ms = (body.punched_at - epoch_ms(record["punch_in"]))
    if duration_ms <= 0:
        raise HTTPException(status_code=422,detail="Punch-out must be after punch-in",)
    if duration_ms > 86_400_000:
        raise HTTPException(status_code=422,detail="Punch duration exceeds 24 hours",)
    else:
        elapsed = ts - punch_in_ist

    if elapsed.total_seconds() <= 0:
        raise HTTPException(status_code=422,detail="Punch-out must be after punch-in",)

    if elapsed > timedelta(hours=24):
        raise HTTPException(status_code=422,detail="Punch duration exceeds 24 hours",)
    work_hours = compute_work_hours(punch_in_ist,ts)
    overtime_minutes = compute_overtime(punch_out=ts,shift_start=emp["shift_start"],shift_end=emp["shift_end"],date_str=record["date"])
    if work_hours< 4.5:
        half_day = True
    else:
        half_day = False
    result = db.attendance_logs.update_one({"emp_code":body.emp_code,"date":record["date"],"punch_in":record["punch_in"],"punch_out":None},{"$set":{"punch_out":ts,"work_hours":work_hours,"overtime_minutes":overtime_minutes,"half_day":half_day,}},)
    if result.modified_count != 1:
        raise HTTPException(409, "Aldredy Punched out")
    updated = db.attendance_logs.find_one(
        {
            "emp_code": body.emp_code,
            "date": record["date"],
        },
        {"_id": 0},
    )

    updated["punch_in"] = int(to_ist(updated["punch_in"]).timestamp() * 1000)
    updated["punch_out"] = int(to_ist(updated["punch_out"]).timestamp() * 1000)

    updated.setdefault("history", [])
    updated.setdefault("half_day", False)

    return updated

    
        
    
from fastapi import FastAPI, HTTPException, Query
AttendanceStatus = Literal["PRESENT","WFH","ON_DUTY","ABSENT","LEAVE",]
@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[AttendanceStatus] = None,
    page: int = Query(1,ge=1),
    page_size: int = Query(20,ge=1,le=100),
):
    if date_from and date_to and (date_from > date_to):
        raise HTTPException(422,"date_from must not be after date_to")
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from.isoformat()
        if date_to:
            q["date"]["$lte"] = date_to.isoformat()
    if status:
        q["status"] = status
    total = db.attendance_logs.count_documents(q)
    docs = list(
        db.attendance_logs.find(q, {"_id": 0}).sort([("date", -1), ("emp_code", 1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    for doc in docs:
        for field in ("punch_in", "punch_out"):
            if doc.get(field) is not None:
                doc[field] = epoch_ms(doc[field])

    return {
        "items": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from pymongo import ReturnDocument


PRESENT_STATUSES = {"PRESENT", "WFH", "ON_DUTY"}
NON_PRESENT_STATUSES = {"ABSENT", "LEAVE"}


@app.patch("/attendance/{emp_code}/{date}")
def regularize_attendance(
    emp_code: str,
    date: date,
    request: RegularizeRequest,
):
    employee = db.employees.find_one({"emp_code": emp_code})

    if employee is None:
        raise HTTPException(404, "Employee not found")

    record = db.attendance_logs.find_one({
        "emp_code": emp_code,
        "date": date.isoformat(),
    })

    if record is None:
        raise HTTPException(404, "Attendance record not found")

    changes_requested = request.model_fields_set

    # Validate explicit status values.
    if "status" in changes_requested:
        if request.status is None:
            raise HTTPException(422, "status cannot be null")

    # Validate epoch milliseconds and convert timestamps to UTC.
    new_in = record.get("punch_in")
    new_out = record.get("punch_out")

    for field in ("punch_in", "punch_out"):
        if field in changes_requested:
            value = getattr(request, field)

            if value is not None:
                if value < 100_000_000_000:
                    raise HTTPException(422, f"{field} must be epoch milliseconds")

                # StrictInt in RegularizeRequest rejects floats and strings.
                # datetime.fromtimestamp also rejects out-of-range values.
                try:
                    converted = datetime.fromtimestamp(
                        value / 1000, tz=timezone.utc
                    ).replace(microsecond=0)
                except (ValueError, OverflowError, OSError):
                    raise HTTPException(422, f"{field} is outside the supported timestamp range")

                if field == "punch_in":
                    new_in = converted
                else:
                    new_out = converted
            else:
                if field == "punch_in":
                    new_in = None
                else:
                    new_out = None

    old_status = record.get("status")
    old_in = record.get("punch_in")
    old_out = record.get("punch_out")

    new_status = (request.status if "status" in changes_requested else old_status)

    # Normalize stored BSON datetimes (PyMongo may return naive UTC).
    def as_utc(value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    old_in = as_utc(old_in)
    old_out = as_utc(old_out)
    new_in = as_utc(new_in)
    new_out = as_utc(new_out)

    # ABSENT and LEAVE cannot be supplied with punch times.
    if new_status in NON_PRESENT_STATUSES:
        if ("punch_in" in changes_requested and request.punch_in is not None):
            raise HTTPException(422, "ABSENT or LEAVE cannot have punch times")

        if ("punch_out" in changes_requested and request.punch_out is not None):
            raise HTTPException(422, "ABSENT or LEAVE cannot have punch times")

        new_in = None
        new_out = None

    # Presence statuses require punch-in.
    if new_status in PRESENT_STATUSES and new_in is None:
        raise HTTPException(422, "A presence status requires punch_in")

    # R1: validate attendance date, including overnight shifts.
    if new_in is not None:
        punch_in_ist = to_ist(new_in)

        start_h, start_m = map(
            int, employee["shift_start"].split(":")
        )
        end_h, end_m = map(
            int, employee["shift_end"].split(":")
        )

        expected_date = punch_in_ist.date()

        # Overnight shift: early-morning punch-in belongs
        # to the previous day's shift.
        if (end_h, end_m) <= (start_h, start_m):
            if (
                punch_in_ist.hour,
                punch_in_ist.minute,
            ) < (end_h, end_m):
                expected_date -= timedelta(days=1)

        if expected_date != date:
            raise HTTPException(422, "punch_in must be on the attendance date")

    # R1: calculations use timestamps truncated to whole seconds.
    # R4/R5: validate punch-out and calculate duration.
    if new_out is not None:
        if new_in is None:
            raise HTTPException(422, "punch_out requires punch_in")

        elapsed_seconds = (new_out - new_in).total_seconds()

        if elapsed_seconds <= 0 or elapsed_seconds > 24 * 60 * 60:
            raise HTTPException(422,"punch_out must be after punch_in and within 24 hours",)

    # Capture changes to the directly editable fields.
    changes = {}

    for field, old_value, new_value in (
        ("status", old_status, new_status),
        ("punch_in", old_in, new_in),
        ("punch_out", old_out, new_out),
    ):
        if old_value != new_value:
            changes[field] = {
                "from": (
                    epoch_ms(old_value)
                    if isinstance(old_value, datetime)
                    else old_value
                ),
                "to": (
                    epoch_ms(new_value)
                    if isinstance(new_value, datetime)
                    else new_value
                ),
            }

    shift_start = employee["shift_start"]
    shift_end = employee["shift_end"]

    # R2: recalculate late minutes from the final punch-in.
    late_minutes = (
        compute_late_minutes(
            new_in, shift_start, shift_end
        )
        if new_in is not None
        else 0
    )

    # R3-R5: recalculate all derived fields from final timestamps.
    if new_in is not None and new_out is not None:
        work_hours = compute_work_hours(new_in, new_out)

        overtime_minutes = compute_overtime(
            new_out,
            shift_start,
            shift_end,
            date.isoformat(),
        )

        half_day = work_hours < 4.50
    else:
        work_hours = None
        overtime_minutes = 0
        half_day = False

    derived = {
        "late_minutes": late_minutes,
        "work_hours": work_hours,
        "overtime_minutes": overtime_minutes,
        "half_day": half_day,
    }

    # Add only derived values that actually changed to the audit trail.
    defaults = {
        "late_minutes": 0,
        "work_hours": None,
        "overtime_minutes": 0,
        "half_day": False,
    }

    for field, new_value in derived.items():
        old_value = record.get(field, defaults[field])

        if old_value != new_value:
            changes[field] = {
                "from": old_value,
                "to": new_value,
            }

    if not changes:
        raise HTTPException(422, "The request does not change anything")

    # R1: normalize the audit timestamp to whole seconds.
    history_entry = {
        "at": datetime.now(timezone.utc).replace(microsecond=0),
        "by": request.regularized_by,
        "reason": request.reason,
        "changes": changes,
    }

    update_fields = {
        "status": new_status,
        "punch_in": new_in,
        "punch_out": new_out,
        **derived,
    }

    # Optimistic concurrency: update only if the original record
    # still has the values read above.
    filter_query = {
        "emp_code": emp_code,
        "date": date.isoformat(),
    }

    for field in ("status", "punch_in", "punch_out"):
        if field in record:
            filter_query[field] = record[field]
        else:
            filter_query[field] = {"$exists": False}

    # Also guard against concurrent changes to derived values so
    # corrections cannot silently overwrite one another.
    for field in (
        "late_minutes",
        "work_hours",
        "overtime_minutes",
        "half_day",
    ):
        if field in record:
            filter_query[field] = record[field]
        else:
            filter_query[field] = {"$exists": False}

    try:
        updated = db.attendance_logs.find_one_and_update(filter_query,{"$set": update_fields,"$push": {"history": history_entry},},return_document=ReturnDocument.AFTER,)
    except Exception:
        raise

    if updated is None:
        raise HTTPException(409, "Attendance record changed concurrently; retry")

    # API responses must not expose MongoDB's internal _id.
    updated.pop("_id", None)

    # Convert all top-level instants to epoch milliseconds.
    for field in ("punch_in", "punch_out"):
        if updated.get(field) is not None:
            updated[field] = epoch_ms(updated[field])

    # Legacy records may not have these fields.
    updated.setdefault("history", [])
    updated.setdefault("half_day", False)
    updated.setdefault("late_minutes", 0)
    updated.setdefault("overtime_minutes", 0)

    # Convert audit timestamps and nested punch-time values.
    for entry in updated["history"]:
        if isinstance(entry.get("at"), datetime):
            entry["at"] = epoch_ms(entry["at"])

        for change in entry.get("changes", {}).values():
            for side in ("from", "to"):
                value = change.get(side)
                if isinstance(value, datetime):
                    change[side] = epoch_ms(value)

    return updated


import calendar, re

def count_working_days(start_date: date, end_date: date) -> int:
    """Count Monday-Friday dates, inclusive."""
    if start_date > end_date:
        return 0

    year, month = start_date.year, start_date.month
    weeks = calendar.monthcalendar(year, month)

    total = 0
    for week in weeks:
        for weekday in range(5):  # Monday-Friday
            day = week[weekday]
            if day and start_date.day <= day <= end_date.day:
                total += 1

    return total


def round_half_up(value: float, places: int) -> float:
    quantum = Decimal("1").scaleb(-places)
    return float(
        Decimal(str(value)).quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    )


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(
    emp_code: str,
    month: str = Query(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
):
    # 1. Verify the employee exists.
    employee = db.employees.find_one(
        {"emp_code": emp_code},
        {"_id": 0, "emp_code": 1, "joined_on": 1},
    )

    if employee is None:
        raise HTTPException(status_code=404,detail="Employee not found",)
    # 2. Determine the calendar month boundaries.
    year, month_number = map(int, month.split("-"))
    month_start = date(year, month_number, 1)
    if month_number == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month_number + 1, 1)
    month_end = next_month_start - timedelta(days=1)

    # 3. Apply R7: working days start no earlier than joined_on.
    joined_on = date.fromisoformat(employee["joined_on"])
    effective_start = max(month_start, joined_on)

    working_days = (count_working_days(effective_start, month_end)if effective_start <= month_end else 0)

    # 4. Summarize attendance in MongoDB.
    pipeline = [{"$match": {"emp_code": emp_code,"date": {"$gte": month_start.isoformat(),"$lt": next_month_start.isoformat(),},}},
    {"$group": {"_id": None,"present_days": {"$sum": {"$cond": [{"$and": [{"$in": ["$status",["PRESENT", "WFH", "ON_DUTY"],]},{"$in": [{"$dayOfWeek": {"$dateFromString": {"dateString": "$date"}}},[2, 3, 4, 5, 6],]},]},{"$cond": [{"$eq": ["$half_day", True]},0.5,1,]},0,]}},
            "leave_days": {"$sum": {"$cond": [{"$eq": ["$status", "LEAVE"]},1,0,]}},
            "late_count": {"$sum": {"$cond": [{"$gt": [{"$ifNull": ["$late_minutes", 0]}, 0]},1,0,]}},
            "total_late_minutes": {"$sum": {"$ifNull": ["$late_minutes", 0]}},
            "total_overtime_minutes": {"$sum": {"$ifNull": ["$overtime_minutes", 0]}},
    }},]
    result = next(iter(db.attendance_logs.aggregate(pipeline)), None)
    # 5. Employees can have zero attendance records in the month.
    if result is None:
        result = {
            "present_days": 0,
            "leave_days": 0,
            "late_count": 0,
            "total_late_minutes": 0,
            "total_overtime_minutes": 0,
        }

    present_days = round_half_up(result["present_days"], 2)

    # 6. R8: percentage uses four-decimal half-up rounding.
    attendance_pct = (
        round_half_up(
            present_days * 100 / working_days,
            4,
        )
        if working_days > 0
        else None
    )

    # 7. Return only the contracted response fields.
    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": result["leave_days"],
        "late_count": result["late_count"],
        "total_late_minutes": result["total_late_minutes"],
        "total_overtime_minutes": result["total_overtime_minutes"],
        "attendance_pct": attendance_pct,
    }


@app.get("/analytics/departments/summary")
def department_summary(month: str = Query(...,pattern=r"^\d{4}-(0[1-9]|1[0-2])$",),department: Optional[str] = None,):
    year, month_number = map(int, month.split("-"))
    month_start = date(year, month_number, 1)

    if month_number == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month_number + 1, 1)

    month_end = next_month_start - timedelta(days=1)

    # Start from employees so employees without attendance logs count.
    employee_match = {"joined_on": {"$lte": month_end.isoformat()}}
    if department is not None:
        employee_match["department"] = department

    pipeline = [
{"$match": employee_match},
{"$lookup": {
"from": "attendance_logs",
"let": {"employee_code": "$emp_code"},
"pipeline": [
{"$match": {"$expr": {"$and": [
{"$eq": ["$emp_code", "$$employee_code"]},
{"$gte": ["$date", month_start.isoformat()]},
{"$lt": ["$date", next_month_start.isoformat()]}
]}}},
{"$set": {
"_attendance_date": {"$dateFromString": {"dateString": "$date"}},
"_late": {"$ifNull": ["$late_minutes", 0]}
}}
],
"as": "logs"
}},
{"$unwind": {"path": "$logs", "preserveNullAndEmptyArrays": True}},
{"$group": {
"_id": {"department": "$department", "emp_code": "$emp_code"},
"headcount": {"$first": 1},
"present_days": {"$sum": {"$cond": [
{"$and": [
{"$in": ["$logs.status", ["PRESENT", "WFH", "ON_DUTY"]]},
{"$in": [{"$dayOfWeek": "$logs._attendance_date"}, [2, 3, 4, 5, 6]]}
]},
{"$cond": [{"$eq": ["$logs.half_day", True]}, 0.5, 1]},
0
]}},
"work_hours_sum": {"$sum": {"$cond": [
{"$and": [
{"$in": ["$logs.status", ["PRESENT", "WFH", "ON_DUTY"]]},
{"$ne": ["$logs.work_hours", None]}
]},
"$logs.work_hours",
0
]}},
"work_hours_count": {"$sum": {"$cond": [
{"$and": [
{"$in": ["$logs.status", ["PRESENT", "WFH", "ON_DUTY"]]},
{"$ne": ["$logs.work_hours", None]}
]},
1,
0
]}},
"late_count": {"$sum": {"$cond": [{"$gt": ["$logs._late", 0]}, 1, 0]}},
"total_late_minutes": {"$sum": "$logs._late"},
"leave_count": {"$sum": {"$cond": [{"$eq": ["$logs.status", "LEAVE"]}, 1, 0]}},
"on_duty_count": {"$sum": {"$cond": [{"$eq": ["$logs.status", "ON_DUTY"]}, 1, 0]}}
}},
{"$group": {
"_id": "$_id.department",
"headcount": {"$sum": "$headcount"},
"present_days": {"$sum": "$present_days"},
"work_hours_sum": {"$sum": "$work_hours_sum"},
"work_hours_count": {"$sum": "$work_hours_count"},
"late_count": {"$sum": "$late_count"},
"total_late_minutes": {"$sum": "$total_late_minutes"},
"leave_count": {"$sum": "$leave_count"},
"on_duty_count": {"$sum": "$on_duty_count"}
}},
{"$sort": {"_id": 1}}
]

    rows = list(db.employees.aggregate(pipeline))

    items = []
    for row in rows:
        count = row["work_hours_count"]

        avg_work_hours = (round_half_up(row["work_hours_sum"] / count, 2)if count > 0 else None)
        items.append({
            "department": row["_id"],
            "headcount": row["headcount"],
            "present_days": round_half_up(row["present_days"], 2),
            "avg_work_hours": avg_work_hours,
            "late_count": row["late_count"],
            "total_late_minutes": row["total_late_minutes"],
            "leave_count": row["leave_count"],
            "on_duty_count": row["on_duty_count"],
        })

    return {
        "month": month,
        "items": items,
    }


@app.get("/analytics/leaderboard/late")
def late_leaderboard(
    month: str = Query(...,pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None,):

    year, month_number = map(int, month.split("-"))

    month_start = date(year, month_number, 1)

    if month_number == 12:
        next_month_start = date(year + 1, 1, 1)
    else:
        next_month_start = date(year, month_number + 1, 1)

    pipeline = [{"$match": {"date": {"$gte": month_start.isoformat(),"$lt": next_month_start.isoformat(),}}},
        {"$set": {"_late_minutes": {"$ifNull": ["$late_minutes", 0]}}},
        {"$group": {"_id": "$emp_code","total_late_minutes": {"$sum": "$_late_minutes"},
                "late_count": {"$sum": {"$cond": [{"$gt": ["$_late_minutes", 0]},1,0,]}},}
        },
        {"$match": {"total_late_minutes": {"$gt": 0}}},
        {"$lookup": {"from": "employees","localField": "_id","foreignField": "emp_code","as": "employee",}},
        {"$unwind": "$employee"},
    ]
    # Apply the department filter before ranking.
    if department is not None:
        pipeline.append({"$match": {"employee.department": department}})
    pipeline.extend([{"$set": {"emp_code": "$_id","name": "$employee.name","department": "$employee.department",}},
        {"$setWindowFields": {"sortBy": {"total_late_minutes": -1},"output": {"rank": {"$rank": {}}},}},
        # Filter by rank, not by array position.
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1,"emp_code": 1,}},
        {"$project": {
                "_id": 0,
                "rank": 1,
                "emp_code": 1,
                "name": 1,
                "department": 1,
                "total_late_minutes": 1,
                "late_count": 1,
            }
        },
    ])

    items = list(db.attendance_logs.aggregate(pipeline))

    return {
        "month": month,
        "items": items,
    }


from datetime import date, datetime, time, timedelta


@app.get("/analytics/departments/{department}/trend")
def department_trend(
    department: str,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
):
    if to_date < from_date:
        raise HTTPException(
            status_code=422,
            detail="'to' must be on or after 'from'",
        )

    if (to_date - from_date).days + 1 > 92:
        raise HTTPException(
            status_code=422,
            detail="Date range must not exceed 92 days",
        )

    # A department is valid if any employee belongs to it.
    if db.employees.find_one(
        {"department": department},
        {"_id": 1},
    ) is None:
        raise HTTPException(
            status_code=404,
            detail="Department not found",
        )

    start_datetime = datetime.combine(from_date, time.min)
    end_exclusive = datetime.combine(to_date + timedelta(days=1),time.min,)

    pipeline = build_department_trend_pipeline(department,start_datetime,end_exclusive,)

    rows = list(db.aggregate(pipeline))

    return {
        "department": department,
        "items": rows,
    }


def build_department_trend_pipeline(department: str,start_datetime: datetime,end_exclusive: datetime,):
    return [
        {"$documents": [{"_day": start_datetime},],},
        {"$densify": {"field": "_day","range": {"step": 1,"unit": "day","bounds": [start_datetime, end_exclusive],},},},
        {"$set": {"_date": {"$dateToString": {"format": "%Y-%m-%d","date": "$_day","timezone": "UTC",},},},},
        {"$lookup": {
                "from": "employees",
                "let": {
                    "requested_department": department,
                },
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$department","$$requested_department",],},},},
                    {"$project": {"_id": 0,"emp_code": 1,"joined_on": 1,},},
                ],
                "as": "_employees",
            },
        },
        {"$lookup": {
                "from": "attendance_logs",
                "let": {
                    "current_date": "$_date",
                    "employee_codes": "$_employees.emp_code",
                },
                "pipeline": [
                    {"$match": {"$expr": {"$and": [{"$eq": ["$date","$$current_date",],},{"$in": ["$emp_code","$$employee_codes",],},],},},},
                    {"$project": {"_id": 0,"status": 1,"half_day": 1,"late_minutes": 1,},},
                ],
                "as": "_logs",
            },
        },
        {
            "$set": {
                "is_working_day": {
                    "$in": [
                        {"$dayOfWeek": "$_day"},
                        [2, 3, 4, 5, 6],
                    ],
                },
                "headcount": {
                    "$size": {
                        "$filter": {
                            "input": "$_employees",
                            "as": "employee",
                            "cond": {
                                "$lte": [
                                    "$$employee.joined_on",
                                    "$_date",
                                ],
                            },
                        },
                    },
                },
                "present_count": {
                    "$sum": {
                        "$map": {"input": "$_logs","as": "log","in": {"$cond": [{"$in": ["$$log.status",["PRESENT","WFH","ON_DUTY",],],},
                                    {"$cond": [{"$eq": ["$$log.half_day",True,],},0.5,1,],},0,],},},},},"late_count": {"$size": {"$filter": {"input": "$_logs","as": "log","cond": {"$gt": [{"$ifNull": ["$$log.late_minutes",0,],},0,],},},},},},
        },
        {"$set": {"attendance_rate": {"$cond": [
                        {"$and": ["$is_working_day",{"$gt": ["$headcount", 0]},],},
                        {"$divide": [{"$floor": {"$add": [{"$multiply": [{"$divide": ["$present_count","$headcount",],},10000,],},0.5,],},},10000,],},None,],},},
        },
        {"$setWindowFields": {"sortBy": {"_day": 1},"output": {"moving_avg_7d": {"$avg": "$attendance_rate","window": {"documents": [-6, 0],},},},},},
        {
            "$set": {"moving_avg_7d": {"$cond": [{"$eq": ["$moving_avg_7d", None]},None,{"$divide": [{"$floor": {"$add": [{"$multiply": ["$moving_avg_7d",10000,],},0.5,],},},10000,],},],},},
        },
        {
            "$project": {
                "_id": 0,
                "date": "$_date",
                "is_working_day": 1,
                "headcount": 1,
                "present_count": 1,
                "late_count": 1,
                "attendance_rate": 1,
                "moving_avg_7d": 1,
            },
        },
        {"$sort": {"date": 1,},},
    ]
from typing import Literal
from datetime import date
import re


@app.get("/admin/explain/{endpoint}")
def explain_endpoint(
    endpoint: Literal[
        "attendance_list",
        "employee_monthly",
        "department_summary",
        "late_leaderboard",
        "department_trend",
    ],
    emp_code: Optional[str] = None,
    month: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),):
    def require_params(*names):
        values = {"emp_code": emp_code,"month": month,"department": department,"date_from": date_from,"date_to": date_to,"from": from_date,"to": to_date,}
        missing = [name for name in names if values[name] is None or values[name] == ""]
        if missing:
            raise HTTPException(status_code=422,detail=[{"type": "missing","loc": ["query", name],"msg": "Field required","input": None,}for name in missing],)
    def validate_month():
        if month is not None and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise HTTPException(422, "month must use YYYY-MM format")

    def run_find_explain(collection, query, sort, skip, limit_value):
        command = {
            "find": collection.name,
            "filter": query,
            "sort": dict(sort),
            "skip": skip,
            "limit": limit_value,
        }
        return collection.database.command("explain",command,verbosity="executionStats",)

    def run_aggregate_explain(collection, pipeline):
        command = {"aggregate": 1,
            "pipeline": pipeline,
            "cursor": {},
        }
        return collection.database.command(
            "explain",
            command,
            verbosity="executionStats",
        )

    if endpoint == "attendance_list":
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must not be after date_to")

        query = {}

        if emp_code is not None:
            query["emp_code"] = emp_code

        if date_from is not None or date_to is not None:
            query["date"] = {}
            if date_from is not None:
                query["date"]["$gte"] = date_from.isoformat()
            if date_to is not None:
                query["date"]["$lte"] = date_to.isoformat()

        if status is not None:
            query["status"] = status

        collection = db.attendance_logs
        explain = run_find_explain(
            collection,
            query,
            [("date", -1), ("emp_code", 1)],
            (page - 1) * page_size,
            page_size,
        )

    elif endpoint == "employee_monthly":
        require_params("emp_code", "month")
        validate_month()

        year, month_number = map(int, month.split("-"))
        month_start = date(year, month_number, 1)

        if month_number == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month_number + 1, 1)

        pipeline = [{"$match": {"emp_code": emp_code,
                    "date": {"$gte": month_start.isoformat(),"$lt": next_month_start.isoformat(),},}},
            {"$group": {"_id": "$emp_code","records": {"$sum": 1},}},]
        collection = db.attendance_logs
        explain = run_aggregate_explain(collection, pipeline)

    elif endpoint == "department_summary":
        require_params("month")
        validate_month()
        year, month_number = map(int, month.split("-"))
        month_start = date(year, month_number, 1)

        if month_number == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month_number + 1, 1)

        month_end = next_month_start - timedelta(days=1)

        employee_match = {
            "joined_on": {"$lte": month_end.isoformat()}
        }

        if department is not None:
            employee_match["department"] = department

        pipeline = [{"$match": employee_match},{
                "$lookup": {"from": "attendance_logs","let": {"employee_code": "$emp_code"},
                    "pipeline": [{"$match": {"$expr": {"$and": [{"$eq": ["$emp_code","$$employee_code",]},
                                        {"$gte": ["$date",month_start.isoformat(),]},
                                        {"$lt": ["$date",next_month_start.isoformat(),]},]}}}],"as": "logs",}},
            {"$unwind": {"path": "$logs","preserveNullAndEmptyArrays": True,}},
            {"$group": {"_id": "$department","records": {"$sum": 1},}},
            {"$sort": {"_id": 1}},
        ]

        collection = db.employees
        explain = run_aggregate_explain(collection, pipeline)

    elif endpoint == "late_leaderboard":
        require_params("month")
        validate_month()

        year, month_number = map(int, month.split("-"))
        month_start = date(year, month_number, 1)

        if month_number == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month_number + 1, 1)

        pipeline = [{"$match": {"date": {"$gte": month_start.isoformat(),"$lt": next_month_start.isoformat(),}}},
            {"$set": {"_late_minutes": {"$ifNull": ["$late_minutes", 0]}}},
            {"$group": {"_id": "$emp_code","total_late_minutes": {"$sum": "$_late_minutes"},
                    "late_count": {"$sum": {"$cond": [{"$gt": ["$_late_minutes", 0]},1,0,]}},}},
            {"$match": {"total_late_minutes": {"$gt": 0}}},
            {"$lookup": {"from": "employees","localField": "_id","foreignField": "emp_code","as": "employee",}},
            {"$unwind": "$employee"},]

        if department is not None:
            pipeline.append({"$match": {"employee.department": department}})
        pipeline.extend([{"$setWindowFields": {"sortBy": {"total_late_minutes": -1},"output": {"rank": {"$rank": {}}},}},
            {"$match": {"rank": {"$lte": limit}}},
            {"$sort": {"total_late_minutes": -1,"emp_code": 1,}},
        ])

        collection = db.attendance_logs
        explain = run_aggregate_explain(collection, pipeline)

    else:  # department_trend
        require_params("department", "from", "to")

        if to_date < from_date:
            raise HTTPException(422, "'to' must be on or after 'from'")

        if (to_date - from_date).days + 1 > 92:
            raise HTTPException(422, "Date range must not exceed 92 days")

        # The trend endpoint uses a database-level aggregation
        # beginning with $documents and $densify.
        # Reuse the EXACT trend pipeline from department_trend().
        raise HTTPException(status_code=501,detail=("Wire the exact department_trend pipeline into ""run_aggregate_explain(db, pipeline) before testing."),)
    return {
        "endpoint": endpoint,
        "collection": collection.name,
        "explain": explain,
    }

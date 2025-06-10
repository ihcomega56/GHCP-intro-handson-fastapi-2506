import json
import os
import uuid
import csv
import re
from datetime import datetime
from io import StringIO
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(
    title="Chaos Kakeibo API",
    description="家計簿データを管理する API",
    version="0.1.0",
)

# ----------------------------------------------------------------------------
# Pydantic Models for Type Safety
# ----------------------------------------------------------------------------

class Entry(BaseModel):
    id: Optional[str] = None
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    category: Optional[str] = "未分類"
    description: Optional[str] = ""
    amount: float

    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, v):
        if v is None or v == "":
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            raise ValueError("amount must be a valid number")

class EntrySummary(BaseModel):
    total: int
    total_amount: str  # Keep as string for backward compatibility
    categories: Dict[str, float]
    entries: List[Dict[str, Any]]  # Keep original format for backward compatibility

# ----------------------------------------------------------------------------
# 疑似データベース（グローバル変数）
# ----------------------------------------------------------------------------
DATA: List[Dict[str, Any]] = []

# ----------------------------------------------------------------------------
# 起動時／終了時の永続化
# ----------------------------------------------------------------------------

@app.on_event("startup")
async def load_data() -> None:
    global DATA
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as fp:
                DATA = json.load(fp)
            print(f"Loaded {len(DATA)} records from data.json")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to load data.json: {exc}")
            DATA = []
    else:
        print("No data.json found – starting fresh")


@app.on_event("shutdown")
async def save_data() -> None:
    with open("data.json", "w", encoding="utf-8") as fp:
        json.dump(DATA, fp, ensure_ascii=False, indent=2)
    print(f"Saved {len(DATA)} records → data.json")

@app.get("/")
async def root_entries():
    return RedirectResponse("/entries", status_code=307)


@app.post("/")
async def root_post(entries: List[Dict[str, Any]]):
    return await create_entries(entries)

# ----------------------------------------------------------------------------
# ヘルスチェック
# ----------------------------------------------------------------------------

@app.get("/healthz")
async def health_check():
    return {"status": "ok", "data_count": len(DATA)}

@app.post("/entries")
async def create_entries(entries: List[Dict[str, Any]]):
    global DATA
    created: List[Dict[str, Any]] = []
    for entry in entries:
        entry.setdefault("id", str(uuid.uuid4()))
        if not entry.get("date") or not entry.get("amount"):
            raise HTTPException(400, "date と amount は必須です")
        entry.setdefault("category", "未分類")
        entry.setdefault("description", "")
        DATA.append(entry)
        created.append(entry)

    # データ上限 10k 件
    if len(DATA) > 10_000:
        DATA[:] = DATA[-10_000:]

    return {"status": "success", "created": len(created), "entries": created}

@app.post("/entries/upload")
async def create_entries_csv(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8")
    reader = csv.DictReader(StringIO(text))
    payload = [row for row in reader]
    return await create_entries(payload)

@app.get("/entries", response_model=EntrySummary)
async def filter_entries(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """Filter entries with improved type safety and validation."""
    # Validate date parameters if provided
    if date_from and not _is_valid_date_format(date_from):
        raise HTTPException(400, "date_from must be in YYYY-MM-DD format")
    if date_to and not _is_valid_date_format(date_to):
        raise HTTPException(400, "date_to must be in YYYY-MM-DD format")

    # Filter entries based on criteria
    filtered_entries = []
    for entry in DATA:
        # Date range filters
        if date_from and entry.get("date", "") < date_from:
            continue
        if date_to and entry.get("date", "") > date_to:
            continue
        # Category filter
        if category and entry.get("category") != category:
            continue
        filtered_entries.append(entry)

    # Calculate total amount with proper error handling
    total_amount = 0.0
    for entry in filtered_entries:
        try:
            amount_value = entry.get("amount", 0)
            if amount_value is not None and amount_value != "":
                total_amount += float(amount_value)
        except (ValueError, TypeError):
            # Skip invalid amounts but continue processing
            continue

    # Calculate category aggregation
    categories: Dict[str, float] = {}
    for entry in filtered_entries:
        cat = entry.get("category", "未分類")
        try:
            amount_value = entry.get("amount", 0)
            if amount_value is not None and amount_value != "":
                amount = float(amount_value)
                categories[cat] = categories.get(cat, 0.0) + amount
        except (ValueError, TypeError):
            # Skip invalid amounts but continue processing
            continue

    return EntrySummary(
        total=len(filtered_entries),
        total_amount=str(total_amount),
        categories=categories,
        entries=filtered_entries,
    )


def _is_valid_date_format(date_str: str) -> bool:
    """Check if date string is in YYYY-MM-DD format."""
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))

@app.get("/entries")
async def export_entries_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    filtered = DATA
    if date_from:
        filtered = [e for e in filtered if e["date"] >= date_from]
    if date_to:
        filtered = [e for e in filtered if e["date"] <= date_to]
    if category:
        filtered = [e for e in filtered if e["category"] == category]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "date", "category", "description", "amount"])
    writer.writeheader()
    writer.writerows(filtered)

    filename = f"entries_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@app.get("/summary/{year_month}")
async def get_summary(year_month: str):
    if len(year_month) != 7 or year_month[4] != "-":
        raise HTTPException(400, "year_month は YYYY-MM 形式で入力してください")
    monthly = [e for e in DATA if e["date"].startswith(year_month)]
    total_amount = sum(float(e.get("amount", 0) or 0) for e in monthly)
    categories: Dict[str, float] = {}
    for e in monthly:
        amt = float(e.get("amount", 0) or 0)
        categories[e["category"]] = categories.get(e["category"], 0) + amt
    sorted_cats = [
        {
            "category": k,
            "amount": str(v),
            "percentage": str(round(v / total_amount * 100, 2)) if total_amount else "0",
        }
        for k, v in sorted(categories.items(), key=lambda i: i[1], reverse=True)
    ]
    return {
        "year_month": year_month,
        "total_entries": len(monthly),
        "total_amount": str(total_amount),
        "categories": sorted_cats,
    }

# ----------------------------------------------------------------------------
# デモ用：サンプルデータ操作
# ----------------------------------------------------------------------------

# サンプルデータを追加するエンドポイント
@app.post("/sample")
async def seed_sample():
    examples = [
        ("2023-01-15", "食費", "スーパーマーケット", "3500"),
        ("2023-01-20", "交通費", "電車", "1200"),
        ("2023-01-25", "食費", "レストラン", "4800"),
        ("2023-02-05", "日用品", "ドラッグストア", "2600"),
        ("2023-02-10", "交際費", "飲み会", "5000"),
        ("2023-02-15", "食費", "コンビニ", "800"),
        ("2023-03-01", "光熱費", "電気代", "7200"),
        ("2023-03-10", "通信費", "携帯電話", "8000"),
        ("2023-03-15", "食費", "スーパーマーケット", "4200"),
    ]
    for d, c, desc, amt in examples:
        DATA.append({
            "id": str(uuid.uuid4()),
            "date": d,
            "category": c,
            "description": desc,
            "amount": amt,
        })
    return {"status": "success", "added": len(examples), "total": len(DATA)}

# サンプルデータを削除するエンドポイント
@app.post(
    "/clear_data",
    tags=["maintenance"],
    description="全てのデータを削除します。この操作は取り消せません。"
)
async def clear_data(
    confirm: bool = Query(
        False,
        description="この操作を確認するには、confirmパラメータをtrueに設定してください"
    )
):
    global DATA
    if not confirm:
        return {"status": "error", "message": "確認が必要です。?confirm=true を追加してください。"}

    previous_count = len(DATA)
    DATA.clear()
    return {
        "status": "success",
        "cleared": previous_count,
        "message": f"{previous_count}件のデータを削除しました"
    }

# ----------------------------------------------------------------------------
# グローバル例外ハンドラ
# ----------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):
    return JSONResponse(status_code=500, content={"message": f"Unexpected error: {exc}"})

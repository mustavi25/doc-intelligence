import pandas as pd
from app.ingestion.types import PageResult

class SpreadsheetError(Exception):
    pass

MAX_TEXT_CHARS = 200_000

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if df.empty:
        return df
    # header row = first row where most cells are text
    first = df.iloc[0]
    texty = sum(isinstance(v, str) for v in first)
    if texty >= max(1, len(first) // 2):
        df.columns = [str(v).strip() if pd.notna(v) else f"col_{i}" for i, v in enumerate(first)]
        df = df.iloc[1:].reset_index(drop=True)
    else:
        df.columns = [f"col_{i}" for i in range(df.shape[1])]
    return df

def _read_csv(path: str) -> dict:
    last = None
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return {"Sheet1": pd.read_csv(path, sep=None, engine="python", header=None,
                                          encoding=enc, dtype=object)}
        except Exception as e:
            last = e
    raise SpreadsheetError(f"Cannot parse CSV: {last}")

def parse_spreadsheet(path: str, kind: str):
    """Returns (list[PageResult], dict sheet_name -> list[row dict])."""
    try:
        if kind == "csv":
            sheets = _read_csv(path)
        else:
            engine = "openpyxl" if kind == "xlsx" else "xlrd"
            sheets = pd.read_excel(path, sheet_name=None, header=None, engine=engine, dtype=object)
    except SpreadsheetError:
        raise
    except Exception as e:
        raise SpreadsheetError(f"Corrupted or unreadable spreadsheet: {e}")

    pages, rows_by_sheet = [], {}
    for idx, (name, raw) in enumerate(sheets.items(), start=1):
        df = _clean(raw)
        if df.empty:
            pages.append(PageResult(idx, "", "spreadsheet", meta={"sheet": name, "empty": True}))
            continue
        records = [{k: (None if pd.isna(v) else str(v)) for k, v in r.items()}
                   for r in df.to_dict("records")]
        rows_by_sheet[name] = records
        text = "\t".join(df.columns) + "\n" + "\n".join(
            "\t".join("" if v is None else v for v in r.values()) for r in records)
        pages.append(PageResult(idx, text[:MAX_TEXT_CHARS], "spreadsheet",
                                meta={"sheet": name, "rows": len(records), "columns": list(df.columns)}))
    return pages, rows_by_sheet
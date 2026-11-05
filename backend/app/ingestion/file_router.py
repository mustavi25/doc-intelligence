import os, zipfile

def detect_type(path: str, filename: str = "") -> str:
    """Returns: pdf | jpg | png | tiff | xlsx | xls | csv | empty | unknown"""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return "empty"
    with open(path, "rb") as f:
        head = f.read(16)
    ext = os.path.splitext(filename or path)[1].lower()

    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\x89PNG"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                if "xl/workbook.xml" in z.namelist():
                    return "xlsx"
        except zipfile.BadZipFile:
            return "unknown"
        return "unknown"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    if ext in (".csv", ".txt", ".tsv"):
        try:
            with open(path, "rb") as f:
                f.read(4096).decode("utf-8-sig")
            return "csv"
        except UnicodeDecodeError:
            return "csv"   # likely latin-1, spreadsheet parser handles it
    return "unknown"
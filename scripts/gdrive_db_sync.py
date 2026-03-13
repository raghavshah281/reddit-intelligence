#!/usr/bin/env python3
"""
Download or upload the DuckDB file to/from Google Drive using a service account.
Requires: GDRIVE_FILE_ID (Drive file ID of the DuckDB), and either GDRIVE_SA_JSON (raw JSON)
or GDRIVE_SA_PATH (path to service account JSON, default secrets/gdrive-service-account.json).
Usage: python scripts/gdrive_db_sync.py download [--out data/reddit.duckdb]
       python scripts/gdrive_db_sync.py upload [--file data/reddit.duckdb]
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent


def get_credentials():
    """Load service account credentials from env or file."""
    raw = os.environ.get("GDRIVE_SA_JSON")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Invalid GDRIVE_SA_JSON: {e}", file=sys.stderr)
            sys.exit(1)
    path = os.environ.get("GDRIVE_SA_PATH") or str(ROOT / "secrets" / "gdrive-service-account.json")
    if not os.path.isfile(path):
        print(f"Missing credentials: set GDRIVE_SA_JSON or place file at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def download(file_id: str, out_path: str) -> None:
    """Download a Drive file by ID to out_path."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds = get_credentials()
    credentials = service_account.Credentials.from_service_account_info(creds)
    service = build("drive", "v3", credentials=credentials)

    request = service.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    print(f"Downloaded to {out_path}")


def upload(file_id: str, file_path: str) -> None:
    """Upload a local file to the existing Drive file (overwrite)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    creds = get_credentials()
    credentials = service_account.Credentials.from_service_account_info(creds)
    service = build("drive", "v3", credentials=credentials)

    media = MediaFileUpload(file_path, resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()
    print(f"Uploaded {file_path} to Drive file {file_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync DuckDB to/from Google Drive")
    parser.add_argument("action", choices=["download", "upload"], help="download from Drive or upload to Drive")
    parser.add_argument("--out", default="data/reddit.duckdb", help="Output path for download")
    parser.add_argument("--file", default="data/reddit.duckdb", help="Local file path for upload")
    args = parser.parse_args()

    file_id = os.environ.get("GDRIVE_FILE_ID")
    if not file_id:
        print("Set GDRIVE_FILE_ID to the Google Drive file ID of the DuckDB file", file=sys.stderr)
        sys.exit(1)

    if args.action == "download":
        download(file_id, args.out)
    else:
        upload(file_id, args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())

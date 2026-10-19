"""
Kira publish: money.db(수집기 결과) → 앱 스키마 JSON → 암호화 → app/data.enc → git push

흐름:
  codef_collector.py 가 CODEF로 거래를 긁어 money.db에 저장
  → publish.py 가 그걸 읽어 폰 앱이 쓰는 형태로 변환·암호화·푸시
  → GitHub Pages의 PWA가 받아서 네 암호로 복호화해 표시

환경변수:
  KIRA_PASSPHRASE   (필수) 데이터 암호. 폰 앱에서 입력하는 것과 동일해야 함.
  KIRA_DB           money.db 경로 (기본: 이 파일 옆)
  KIRA_DATA_OUT     출력 경로 (기본: ../app/data.enc)
  KIRA_PUSH         "1"이면 git commit+push (기본 1), "0"이면 파일만 생성

실행:  python publish.py
"""

import os
import sys
import json
import sqlite3
import subprocess
import datetime

import kira_crypto

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
except ImportError:
    pass

DB = os.environ.get("KIRA_DB", os.path.join(HERE, "money.db"))
OUT = os.environ.get("KIRA_DATA_OUT", os.path.join(HERE, "..", "app", "data.enc"))
PASSPHRASE = os.environ.get("KIRA_PASSPHRASE", "")
DOW_KR = ["월", "화", "수", "목", "금", "토", "일"]


def build_data() -> dict:
    """money.db의 transactions → 앱 스키마로 변환."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM transactions ORDER BY datetime DESC").fetchall()
    txs = []
    for r in rows:
        dt = r["datetime"] or ""
        date = time = dow = ""
        try:
            d = datetime.datetime.fromisoformat(dt)
            date = f"{d.month:02d}.{d.day:02d}"
            time = f"{d.hour:02d}:{d.minute:02d}"
            dow = DOW_KR[d.weekday()]
        except ValueError:
            pass
        in_amt = r["in_amount"] or 0
        out_amt = r["out_amount"] or 0
        if in_amt > 0:
            kind = "income"
        elif r["is_self_transfer"]:
            kind = "self"
        else:
            kind = "spend"
        t = {
            "id": r["tx_key"],
            "date": date, "dow": dow, "time": time,
            "name": r["counterparty"] or "",
            "cat": r["category"],
            "kind": kind,
        }
        if kind == "income":
            t["in"] = in_amt
        else:
            t["out"] = out_amt
        if r["excluded"]:
            t["excluded"] = True
        txs.append(t)
    conn.close()
    return {
        "updated": datetime.datetime.now().isoformat(timespec="minutes"),
        "transactions": txs,
    }


def main() -> None:
    if not PASSPHRASE:
        sys.exit("환경변수 KIRA_PASSPHRASE 를 설정하세요 (폰 앱 암호와 동일하게).")
    if not os.path.exists(DB):
        sys.exit(f"money.db 가 없습니다: {DB}  (먼저 codef_collector.py 를 실행하세요)")

    data = build_data()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    kira_crypto.encrypt_to_file(data, PASSPHRASE, OUT)
    print(f"암호화 완료: {len(data['transactions'])}건 → {OUT}  (updated {data['updated']})")

    if os.environ.get("KIRA_PUSH", "1") == "1":
        root = os.path.join(HERE, "..")
        subprocess.run(["git", "-C", root, "add", "app/data.enc"], check=True)
        # 변경 없으면 commit이 실패하므로 허용
        c = subprocess.run(["git", "-C", root, "commit", "-m", f"data: sync {data['updated']}"])
        if c.returncode == 0:
            subprocess.run(["git", "-C", root, "push", "-q"], check=True)
            print("push 완료 — 몇 초 뒤 폰 앱에서 새로고침하면 반영됨")
        else:
            print("변경 없음 (push 생략)")


if __name__ == "__main__":
    main()

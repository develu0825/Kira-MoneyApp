"""
기존 data.enc(폰에 올라간 암호화 데이터)에 자동분류를 다시 입힌다.
money.db 없이, 원본 CSV 없이 바로 돌아간다.

흐름:
  data.enc 복호화 → 지출마다 guess_category 적용(이미 분류/사용자지정은 건드리지 않음)
  → 다시 암호화해서 data.enc 저장 → (git push하면 폰에 반영)

사용:  python recategorize.py
       python recategorize.py --push     (자동 커밋+푸시까지)
"""
import os
import sys
import json
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import kira_crypto
from categorize import guess_category

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "app", "data.enc")
PW = os.environ.get("KIRA_PASSPHRASE", "")


def main():
    if not PW:
        sys.exit("KIRA_PASSPHRASE(.env) 가 필요해요.")
    blob = json.load(open(DATA, encoding="utf-8"))
    data = json.loads(kira_crypto.decrypt(blob, PW))
    txs = data.get("transactions", [])

    changed = 0
    for t in txs:
        if not t.get("out"):          # 지출만 분류 (입금/이체는 사용자 판단)
            continue
        if t.get("cat"):              # 이미 분류돼 있으면 보존
            continue
        cat = guess_category(t.get("name", ""))
        if cat:
            t["cat"] = cat
            changed += 1

    kira_crypto.encrypt_to_file(data, PW, DATA)

    spend = [t for t in txs if t.get("out")]
    withcat = [t for t in spend if t.get("cat")]
    print(f"자동분류 적용: 이번에 {changed}건 → 지출 {len(withcat)}/{len(spend)}건 분류됨")

    if "--push" in sys.argv:
        root = os.path.join(HERE, "..")
        subprocess.run(["git", "-C", root, "add", "app/data.enc"], check=True)
        c = subprocess.run(["git", "-C", root, "commit", "-m",
                            f"data: recategorize ({withcat and len(withcat)} categorized)"])
        if c.returncode == 0:
            subprocess.run(["git", "-C", root, "push", "-q"], check=True)
            print("push 완료 — 폰 앱 완전 종료 후 재실행하면 반영")
        else:
            print("변경 없음 (push 생략)")
    else:
        print("폰에 반영하려면:  python recategorize.py --push   (또는 git push)")


if __name__ == "__main__":
    main()

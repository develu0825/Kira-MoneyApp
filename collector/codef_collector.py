"""
CODEF 거래내역 수집기 (카카오뱅크 / 토스 / 신한 등)
------------------------------------------------------------------
목적: CODEF API로 내 계좌 수시입출 거래내역을 하루 1번 긁어서
      로컬 SQLite에 저장한다. iOS 앱은 이 DB만 읽어서 보여준다.

핵심 설계: 이 앱은 "다 가져오는 가계부"가 아니라
           "가져온 것 중 진짜 소비만 남기는" 필터링 앱이다.
           그래서 transactions 테이블에 제외/분류용 컬럼
           (excluded, category, is_self_transfer, memo)을 둔다.
           수집기는 raw 데이터를 넣기만 하고,
           제외/분류 상태는 앱에서 바꿔도 재수집 시 보존된다(UPSERT).

주의: CODEF의 기관별 간편인증 파라미터(아래 CONFIG의 *_AUTH 부분)와
      상품 URL/파라미터 세부 스펙은 기관마다 다르다.
      반드시 https://developer.codef.io 에서 해당 기관 스펙으로 확인/보정할 것.
      (코드 흐름/2-way 인증/DB 저장 로직은 그대로 두고 값만 맞추면 됨)

설치: python -m pip install easycodefpy
실행: python codef_collector.py
"""

import os
import json
import sqlite3
import datetime as dt
from pathlib import Path

from easycodefpy import Codef, ServiceType

# easycodefpy는 RSA 암호화 헬퍼를 제공한다. (import 경로가 다르면 SDK 버전 확인)
try:
    from easycodefpy import encrypt_rsa
except ImportError:  # 일부 버전은 crypto 모듈에 위치
    from easycodefpy.crypto import encrypt_rsa

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


# =====================================================================
# CONFIG  — 여기 값만 본인 환경/기관 스펙에 맞게 채우면 됨
# =====================================================================

# --- CODEF 인증정보 (앱에 넣지 말 것! 이 스크립트/서버에만 둔다) ---
# 콘솔(https://codef.io) → 내 서비스에서 발급.
# 처음엔 DEMO로 테스트 → 정식 전환 시 USE_DEMO=False.
USE_DEMO = True
CLIENT_ID = os.environ.get("CODEF_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CODEF_CLIENT_SECRET", "")
PUBLIC_KEY = os.environ.get("CODEF_PUBLIC_KEY", "")

SERVICE = ServiceType.DEMO if USE_DEMO else ServiceType.API

# --- 저장 위치 ---
DB_PATH = Path(__file__).parent / "money.db"
# ConnectedId는 재사용 가능하므로 캐시해 두고, 만료되면 다시 발급한다.
CONNECTED_ID_CACHE = Path(__file__).parent / ".connected_id.json"

# --- 조회할 계좌/기관 ---
# organization 코드: 카카오뱅크 0090 / 토스뱅크 0092 / 신한 0088
# 카뱅은 앱 전용이라 간편인증(폰 승인)만 가능하다.
def _accounts(*env_keys: str) -> list:
    """쉼표로 구분된 계좌번호 목록 (단수/복수 env 이름 모두 허용). 가상계좌도 번호만 추가."""
    for k in env_keys:
        v = os.environ.get(k, "")
        if v.strip():
            return [a.strip() for a in v.split(",") if a.strip()]
    return []


# 간편인증 사용자 정보 (기관/간편인증수단별로 필요한 키가 다름 → 문서 확인)
_AUTH = {
    "loginType": os.environ.get("LOGIN_TYPE", "5"),             # 5 = 간편인증 (안되면 .env에 LOGIN_TYPE=6 시도)
    "loginTypeLevel": os.environ.get("SIMPLE_AUTH_LEVEL", "1"),  # 1=카카오톡,2=페이코,3=삼성패스,4=KB,5=PASS,6=네이버,7=신한,8=토스
    "userName": os.environ.get("MY_NAME", ""),
    "phoneNo": os.environ.get("MY_PHONE", ""),
    "identity": os.environ.get("MY_BIRTH", ""),                 # 생년월일 YYMMDD (또는 주민번호)
    "telecom": os.environ.get("TELECOM", ""),                   # PASS(5) 간편인증일 때만: 0=SKT,1=KT,2=LGU+
    "id": "",
}

# 은행마다 계좌 여러 개 가능 (가상계좌 포함) — .env에 쉼표로 나열: KAKAO_ACCOUNTS=111,222,가상계좌번호
TARGETS = [
    {"nickname": "카카오뱅크", "organization": "0090",
     "accounts": _accounts("KAKAO_ACCOUNTS", "KAKAO_ACCOUNT"), "auth": dict(_AUTH)},
    {"nickname": "토스뱅크",   "organization": "0092",
     "accounts": _accounts("TOSS_ACCOUNTS", "TOSS_ACCOUNT"),  "auth": dict(_AUTH)},
]

# 내 계좌번호 전체 (상대방이 여기 들어있으면 '자기계좌 이체'로 자동표시 → 소비 제외 후보)
MY_ACCOUNTS = {a for t in TARGETS for a in t["accounts"]}
MY_ACCOUNT_NAMES = {t["nickname"] for t in TARGETS}

# 수시입출 거래내역 상품 URL (★ 실제 경로/파라미터는 문서에서 확인)
TRANSACTION_URL = "/v1/kr/bank/p/account/transaction-list"

# 조회 기간: 최근 N일 (매일 돌리면 중복은 UPSERT로 걸러짐)
LOOKBACK_DAYS = 14


# =====================================================================
# DB
# =====================================================================

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            -- 자연키: 같은 거래가 재수집돼도 한 줄로 유지되도록 구성
            tx_key          TEXT PRIMARY KEY,   -- organization|account|datetime|amount|balance|seq
            organization    TEXT NOT NULL,
            account         TEXT NOT NULL,
            datetime        TEXT NOT NULL,       -- ISO8601
            in_amount       INTEGER DEFAULT 0,   -- 입금액
            out_amount      INTEGER DEFAULT 0,   -- 출금액
            balance         INTEGER,             -- 거래후 잔액
            counterparty    TEXT,                -- 상대/적요/보낸분·받는분
            memo_bank       TEXT,                -- 은행 제공 메모/비고

            -- ↓↓↓ 앱에서 쓰는 '필터링 레이어'. 재수집해도 보존된다. ↓↓↓
            excluded        INTEGER DEFAULT 0,   -- 1이면 '소비 아님'으로 제외
            exclude_reason  TEXT,                -- '지인대여','내계좌이체','환급' 등
            category        TEXT,                -- '식비','교통','구독' 등 분류
            is_self_transfer INTEGER DEFAULT 0,  -- 자동감지: 내 계좌 간 이체 추정
            user_memo       TEXT,                -- 내가 다는 메모

            raw_json        TEXT,                -- 원본(디버깅/재파싱용)
            created_at      TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tx_datetime ON transactions(datetime);
        CREATE INDEX IF NOT EXISTS idx_tx_excluded ON transactions(excluded);
        """
    )
    conn.commit()


def upsert_transaction(conn: sqlite3.Connection, row: dict) -> None:
    """
    재수집 시: raw 필드(금액/잔액/상대)는 갱신하되,
    사용자가 손댄 필드(excluded, exclude_reason, category, user_memo)는 보존.
    is_self_transfer는 자동감지이므로 매번 갱신.
    """
    conn.execute(
        """
        INSERT INTO transactions (
            tx_key, organization, account, datetime,
            in_amount, out_amount, balance, counterparty, memo_bank,
            is_self_transfer, raw_json, created_at
        ) VALUES (
            :tx_key, :organization, :account, :datetime,
            :in_amount, :out_amount, :balance, :counterparty, :memo_bank,
            :is_self_transfer, :raw_json, :created_at
        )
        ON CONFLICT(tx_key) DO UPDATE SET
            in_amount        = excluded.in_amount,
            out_amount       = excluded.out_amount,
            balance          = excluded.balance,
            counterparty     = excluded.counterparty,
            memo_bank        = excluded.memo_bank,
            is_self_transfer = excluded.is_self_transfer,
            raw_json         = excluded.raw_json
        """,
        row,
    )


# =====================================================================
# CODEF
# =====================================================================

def make_codef() -> Codef:
    codef = Codef()
    codef.public_key = PUBLIC_KEY
    if USE_DEMO:
        codef.set_demo_client_info(CLIENT_ID, CLIENT_SECRET)
    else:
        codef.set_client_info(CLIENT_ID, CLIENT_SECRET)
    return codef


def _as_dict(res):
    """easycodefpy는 JSON 문자열을 반환 → dict로 변환."""
    if isinstance(res, str):
        try:
            return json.loads(res)
        except Exception:
            return {}
    return res or {}


def is_two_way_needed(res: dict) -> bool:
    """CF-03002 = 추가(간편)인증 필요."""
    code = (res.get("result") or {}).get("code")
    data = res.get("data") or {}
    return code == "CF-03002" or bool(data.get("continue2Way"))


def extract_two_way_info(res: dict) -> dict:
    """2-way 재요청에 필요한 정보 추출."""
    data = res.get("data") or {}
    return {
        "jobIndex": data.get("jobIndex", 0),
        "threadIndex": data.get("threadIndex", 0),
        "jti": data.get("jti", ""),
        "twoWayTimestamp": data.get("twoWayTimestamp", 0),
    }


def request_with_simple_auth(codef: Codef, url: str, base_param: dict) -> dict:
    """
    간편인증(2-way) 공통 처리.
    1) 1차 요청 → 폰으로 간편인증 푸시가 감 → CF-03002 반환
    2) 사용자가 폰에서 승인 후 Enter
    3) twoWayInfo + simpleAuth=1 로 재요청 → 데이터 수신
    (CODEF 안내: 최대 3회 재시도 가능)
    """
    res = _as_dict(codef.request_product(url, SERVICE, dict(base_param)))

    if not is_two_way_needed(res):
        return res

    two_way = extract_two_way_info(res)
    print(f"\n📱 폰에서 간편인증 요청이 왔습니다. 승인(또는 인증서 서명) 후 Enter를 누르세요.")

    for attempt in range(1, 4):  # 최대 3회
        input(f"   [{attempt}/3] 승인 완료했으면 Enter ▶ ")
        retry_param = dict(base_param)
        retry_param.update(
            {
                "is2Way": True,
                "simpleAuth": "1",          # 1 = 간편인증 완료
                "twoWayInfo": two_way,
            }
        )
        res = _as_dict(codef.request_product(url, SERVICE, retry_param))
        if not is_two_way_needed(res):
            return res
        print("   아직 승인이 확인되지 않았어요. 폰에서 승인했는지 확인 후 다시 Enter.")
        two_way = extract_two_way_info(res) or two_way

    return res  # 3회 실패 시 마지막 응답 반환


def ensure_connected_id(codef: Codef, target: dict) -> str | None:
    """
    ConnectedId를 캐시에서 가져오거나, 없으면 간편인증으로 새로 발급.
    (발급도 2-way 간편인증이 필요할 수 있음)
    """
    cache = {}
    if CONNECTED_ID_CACHE.exists():
        cache = json.loads(CONNECTED_ID_CACHE.read_text(encoding="utf-8"))
    key = target["organization"]
    if cache.get(key):
        return cache[key]

    account = {
        "countryCode": "KR",
        "businessType": "BK",
        "clientType": "P",
        "organization": target["organization"],
        **target["auth"],
    }
    param = {"accountList": [account]}

    # 계좌 등록도 간편인증 2-way가 걸릴 수 있어 동일 패턴으로 처리
    res = _as_dict(codef.create_account(SERVICE, param))
    if is_two_way_needed(res):
        two_way = extract_two_way_info(res)
        print("\n📱 계좌 등록(간편인증) 승인이 폰으로 전송됐습니다.")
        for attempt in range(1, 4):
            input(f"   [{attempt}/3] 승인 완료 후 Enter ▶ ")
            retry = {"accountList": [account], "is2Way": True,
                     "simpleAuth": "1", "twoWayInfo": two_way}
            res = _as_dict(codef.create_account(SERVICE, retry))
            if not is_two_way_needed(res):
                break

    data = res.get("data") or {}
    connected_id = data.get("connectedId")
    if connected_id:
        cache[key] = connected_id
        CONNECTED_ID_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        print(f"✅ ConnectedId 발급/저장 완료 ({target['nickname']})")
    else:
        print(f"⚠️ ConnectedId 발급 실패: {res.get('result')}")
    return connected_id


# =====================================================================
# 파싱 & 자동분류
# =====================================================================

def guess_self_transfer(counterparty: str) -> bool:
    """상대방 문자열에 내 계좌/은행명이 들어가면 자기계좌 이체로 추정."""
    if not counterparty:
        return False
    text = counterparty.replace(" ", "")
    for acc in MY_ACCOUNTS:
        if acc and acc[-6:] in text:  # 끝 6자리 매칭(부분 마스킹 대비)
            return True
    for name in MY_ACCOUNT_NAMES:
        if name and name in counterparty:
            return True
    return False


def parse_and_store(conn: sqlite3.Connection, target: dict, account: str, res: dict) -> int:
    """
    CODEF 응답의 거래내역 리스트를 파싱해 저장.
    ★ 실제 필드명(resTrDate, resTrTime, resAccountOut, resAccountIn,
      resAfterTranBalance, resAccountDesc1~4 등)은 기관/상품 응답 스펙에
      맞춰 아래 매핑을 보정하세요. (여기선 흔한 필드명을 가정)
    """
    data = res.get("data") or {}
    tx_list = data.get("resTrHistoryList") or data.get("list") or []
    now = dt.datetime.now().isoformat()
    count = 0

    for i, t in enumerate(tx_list):
        date = t.get("resAccountTrDate") or t.get("resTrDate") or ""
        time = t.get("resAccountTrTime") or t.get("resTrTime") or "000000"
        when = ""
        if date:
            when = f"{date[:4]}-{date[4:6]}-{date[6:8]}T{time[:2]}:{time[2:4]}:{time[4:6]}"

        out_amt = int((t.get("resAccountOut") or "0").replace(",", "") or 0)
        in_amt = int((t.get("resAccountIn") or "0").replace(",", "") or 0)
        balance = int((t.get("resAfterTranBalance") or "0").replace(",", "") or 0)
        counterparty = (t.get("resAccountDesc3") or t.get("resAccountDesc1")
                        or t.get("resTrDesc") or "").strip()
        memo_bank = (t.get("resAccountDesc2") or "").strip()

        tx_key = f"{target['organization']}|{account}|{when}|{in_amt}|{out_amt}|{balance}|{i}"

        upsert_transaction(conn, {
            "tx_key": tx_key,
            "organization": target["organization"],
            "account": account,
            "datetime": when,
            "in_amount": in_amt,
            "out_amount": out_amt,
            "balance": balance,
            "counterparty": counterparty,
            "memo_bank": memo_bank,
            "is_self_transfer": 1 if guess_self_transfer(counterparty) else 0,
            "raw_json": json.dumps(t, ensure_ascii=False),
            "created_at": now,
        })
        count += 1

    conn.commit()
    return count


# =====================================================================
# main
# =====================================================================

def main() -> None:
    if not (CLIENT_ID and CLIENT_SECRET and PUBLIC_KEY):
        raise SystemExit(
            "환경변수 CODEF_CLIENT_ID / CODEF_CLIENT_SECRET / CODEF_PUBLIC_KEY 를 설정하세요."
        )

    today = dt.date.today()
    start = (today - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    codef = make_codef()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    for target in TARGETS:
        if not target["accounts"]:
            print(f"⏭  {target['nickname']}: 계좌 미설정, 건너뜀")
            continue

        print(f"\n=== {target['nickname']} 수집 시작 ({len(target['accounts'])}개 계좌) ===")
        connected_id = ensure_connected_id(codef, target)   # 은행당 간편인증 1번
        if not connected_id:
            continue

        for account in target["accounts"]:                  # 계좌(가상계좌 포함)마다 조회
            param = {
                "connectedId": connected_id,
                "organization": target["organization"],
                "account": account,
                "startDate": start,
                "endDate": end,
                "orderBy": "0",      # 0=최신순 (문서 확인)
                "inquiryType": "1",  # 조회구분 (문서 확인)
            }
            res = request_with_simple_auth(codef, TRANSACTION_URL, param)
            code = (res.get("result") or {}).get("code")
            if code and code != "CF-00000":  # CF-00000 = 정상
                print(f"⚠️ {account} 응답코드 {code}: {(res.get('result') or {}).get('message')}")
            n = parse_and_store(conn, target, account, res)
            print(f"✅ {target['nickname']} {account}: {n}건 저장/갱신")

    # 간단 요약: '소비로 집계되는' 금액 = 출금 중 제외/자기이체 제외
    cur = conn.execute(
        """
        SELECT
          COALESCE(SUM(out_amount),0) AS total_out,
          COALESCE(SUM(CASE WHEN excluded=0 AND is_self_transfer=0 THEN out_amount ELSE 0 END),0) AS real_spend
        FROM transactions
        WHERE datetime >= ?
        """,
        (f"{start[:4]}-{start[4:6]}-{start[6:8]}",),
    )
    total_out, real_spend = cur.fetchone()
    print(f"\n최근 {LOOKBACK_DAYS}일 ── 총 출금 {total_out:,}원 / 진짜 소비(추정) {real_spend:,}원")
    print("   (제외/자기이체 표시는 iOS 앱에서 조정하면 재수집해도 유지됩니다)")

    conn.close()


if __name__ == "__main__":
    main()

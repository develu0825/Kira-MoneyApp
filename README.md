# Kira — personal money app

내가 **실제로 쓴 돈**만 보여주는 개인 가계부. 보통 가계부와 달리 *모든 걸* 기록하는 게
아니라, 내 다른 계좌로 보낸 이체·지인에게 빌려준 돈처럼 "소비가 아닌 것"을 빼고
**진짜 소비**를 보여준다.

## 구조 (무료·추가 계정 없이)

```
[CODEF] → [PC 수집기] → [AES-256 암호화] → [GitHub(공개레포)] → [폰 PWA]
  은행      money.db       data.enc          git push          복호화해 표시
```

- **CODEF**가 은행 스크래핑을 대신 → 은행별 연동 직접 안 짬
- **PC 수집기**가 하루 1번 거래를 긁어 암호화 후 push
- **폰 PWA**가 `data.enc`를 받아 내 암호로 **복호화해서** 표시
  → 공개 레포라도 데이터는 암호화돼 안전 (AES-256-GCM, 암호 없으면 못 봄)

## 구성

| 경로 | 설명 |
|------|------|
| `app/index.html` | Kira PWA (전체화면, 설치형). GitHub Pages로 호스팅 |
| `app/data.enc` | 암호화된 거래 데이터 (수집기가 생성·push) |
| `app/icons/`, `app/manifest.webmanifest` | 앱 아이콘·PWA 매니페스트 |
| `collector/codef_collector.py` | CODEF → money.db |
| `collector/publish.py` | money.db → 암호화 → data.enc → git push |
| `collector/kira_crypto.py` | AES-256-GCM 암호화 (브라우저 Web Crypto와 호환) |
| `docs/money-app-mockup.html` | 디자인 목업 (= app/index.html 소스) |
| `docs/codef-setup-checklist.md` | CODEF 가입·무료티어·인증 체크리스트 |

## 앱 기능

- **Kira / All 토글** — 진짜 소비 vs 총 출금
- **소비 아님 제외** — 탭/스와이프로 이체·대여 제외 (자기이체 자동감지). 변경은 기기에 저장
- **달 선택** · **카테고리별 목표**(데이트는 교차 태그) · **수입/남는 돈** · **빌려준 돈**(받을 돈) · **통계**
- **PIN 잠금** · 금액 입력 시 콤마+한글 금액 · 다크 모드

## 라이브

- 앱: **https://develu0825.github.io/Kira-MoneyApp/app/**  (아이폰 Safari → 공유 → 홈 화면에 추가)
- 데이터 연결 전에는 샘플(데모) 데이터로 동작

---

## 셋업 (실데이터 연결)

### 1. CODEF 가입 → 키 발급
`docs/codef-setup-checklist.md` 참고. CLIENT_ID / CLIENT_SECRET / PUBLIC_KEY 발급.

### 2. 수집기 설정 (PC)
```bash
pip install -r collector/requirements.txt
cd collector
cp .env.example .env     # .env 에 키·암호·본인정보 입력
```
> `KIRA_PASSPHRASE` 는 **폰 앱에서 입력할 암호와 동일**해야 함. `.env` 는 커밋 금지.

### 3. 수집 + 암호화 + push
```bash
python codef_collector.py   # CODEF → money.db (폰에서 간편인증 승인)
python publish.py           # money.db → data.enc → git push
```
몇 초 뒤 폰 앱을 **완전 종료 후 재실행** → 암호 입력 → 실데이터 표시.

### 4. 매일 자동화 (Windows 작업 스케줄러)
`codef_collector.py` → `publish.py` 를 하루 1회 실행하도록 등록.
단, 카카오뱅크는 간편인증이라 ConnectedId 만료 시 **폰에서 재승인** 필요
(앱 홈의 동기화 버튼 빨간 점으로 안내).

## 보안

- **절대 커밋 금지**: CODEF 키·RSA키·`ConnectedId`·은행 로그인·`money.db`·`.env` (모두 `.gitignore`)
- 데이터는 AES-256-GCM 암호화 후에만 push. 암호(KIRA_PASSPHRASE)는 PC `.env`와 폰에만 존재
- 공개 레포지만 암호 없이는 데이터 복호화 불가. **강한 암호 사용 권장**

## 로드맵

- [x] 디자인/앱 프로토타입 (PWA, 설치형)
- [x] 암호화 파이프라인 (collector ↔ 폰 Web Crypto 호환 검증)
- [x] PIN 잠금 · 기기 저장(제외/분류/목표)
- [ ] CODEF 실연동 (가입 후 키 입력)
- [ ] (선택) SwiftUI 네이티브 (맥 필요)

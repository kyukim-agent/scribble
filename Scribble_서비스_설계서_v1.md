# ✏️ Scribble 서비스 설계서 v1.0

| 항목 | 내용 |
|------|------|
| 서비스명 | Scribble |
| 버전 | v1.0 |
| 연관 서비스 | Memory Courier, People Keeper |
| 채널 | Telegram Bot |
| 백엔드 | FastAPI on Railway |
| LLM | Anthropic Claude API |
| 저장소 | Notion Database |

---

## 1. 서비스 개요

Scribble은 사용자가 일상 속에서 순간적으로 떠오르는 아이디어와 생각을 텔레그램으로 가볍게 전송하면, AI가 자동으로 프로젝트를 분류하고, 태그를 부여하며, 내용을 구조화하여 Notion 데이터베이스에 저장하는 개인 메모 에이전트 서비스입니다.

### 1.1 핵심 가치

- **Capture First** — 아이디어가 떠오른 순간 마찰 없이 기록
- **Organize Later** — AI가 분류·구조화를 대신 처리
- **Retrieve Easily** — 프로젝트·태그 기반으로 언제든지 탐색
- **Connect** — Memory Courier, People Keeper 등 연관 서비스와 태그 링크

---

## 2. 사용자 플로우

### 2.1 전체 플로우 다이어그램

```
[사용자] 텔레그램에서 메모 입력
    │
    ▼
[Telegram Bot] Webhook → Railway 서버 (FastAPI)
    │
    ├─ 명령어(/projects, /add, /del)? → 프로젝트 관리 처리
    │
    └─ 일반 메모 텍스트
          │
          ▼
      [LLM] 프로젝트 자동 분류
          │
          ├─ 분류 성공 → 태그 생성 → 구조화
          │
          └─ 분류 실패 → 사용자에게 재질문 (대화 컨텍스트 유지)
                            │ (사용자 답변 수신)
                            ▼
                       태그 생성 → 구조화
                            │
                            ▼
                   [Notion DB] 메모 저장
                            │
                            ▼
            [Telegram] 피드백 메시지 발송
```

### 2.2 단계별 상세 설명

#### Step 1 — 메모 입력

사용자가 텔레그램의 Scribble Bot 채팅창에 자유 형식으로 메모를 전송합니다. 별도의 형식이나 태그를 요구하지 않으며, 자연어로 작성된 모든 텍스트가 입력으로 처리됩니다.

> **입력 예시**
> - `"MCP 프로토콜을 활용한 에이전트 간 메모리 공유 방법 연구해볼 것"`
> - `"오늘 커피 마시다가 떠오른 아이디어 - 알림 피로도 줄이는 스마트 배치 알고리즘"`
> - `"People Keeper에 태그 기반 검색 붙이면 어떨까?"`

#### Step 2 — Webhook 수신 및 라우팅

Telegram Bot API가 메시지를 Railway의 FastAPI 서버로 Webhook을 통해 전달합니다. 서버는 메시지를 수신한 후 명령어 여부를 판단하여 라우팅합니다.

- `text.startsWith('/')` → 명령어 핸들러 호출
- `pending_context[chat_id]` 존재 → 분류 응답 처리
- 그 외 → 메모 처리 파이프라인 실행

#### Step 3 — LLM 메모 처리 (통합 호출)

Anthropic Claude API를 **1회만** 호출하여 프로젝트 분류, 태그 생성, 내용 구조화를 한 번에 처리합니다. 태그·구조화는 분류 확신도와 무관하게 항상 먼저 완료되며, 이후 분류 결과에 따라 저장 또는 사용자 확인 요청으로 분기합니다.

| 상황 | 처리 방식 |
|------|-----------|
| 분류 성공 (확신도 높음) | 해당 프로젝트로 자동 지정, 바로 Notion 저장 |
| 분류 성공 (확신도 보통) | 태그·구조화 완료 후 후보 2~3개를 Inline keyboard로 제시, 사용자 선택 요청 |
| 분류 실패 (관련 없음) | 태그·구조화 완료 후 LLM이 선별한 상위 5개 프로젝트 + Uncategorized를 Inline keyboard로 제시 (6개 초과 시 '기타 입력' 버튼 추가) |
| 사용자 응답 없음 (5분) | 컨텍스트 만료, `Uncategorized`로 저장 |

#### Step 4 — 대화 컨텍스트 관리

분류 재질문 시 대화 컨텍스트는 서버 인메모리 캐시에 TTL 5분으로 보관합니다. 사용자의 후속 메시지가 분류 응답인지 새 메모인지는 `pending_context` 존재 여부로 판단합니다.

**Pending 충돌 처리 정책**: `pending_context`가 존재하는 상태에서 사용자가 새 메모를 전송하면, 이전 pending 메모는 자동으로 `Uncategorized`로 저장하고 `"이전 메모가 Uncategorized로 저장됐어요."` 알림을 발송한 뒤, 새 메모를 신규 파이프라인으로 처리합니다.

#### Step 5 — 태그 생성

메모의 핵심 키워드, 기술 용어, 인물, 개념 등을 추출하여 태그 배열을 생성합니다. 태그는 Memory Courier, People Keeper와 공유되는 공통 태그 스키마를 따릅니다.

- 최대 태그 수: **5개**
- 형식: 소문자, 하이픈 연결 (한국어 개념은 그대로, 예: `가격경쟁`, `ai-agent`, `BCG`)
- 언어: 콘텐츠 언어를 자연스럽게 따름. 한국어 개념·주제는 한국어로, 영어 고유명사·브랜드는 영어 원어로 유지 (예: `BCG`, `SAP`, `M&A`)

#### Step 6 — 메모 구조화

원문을 보존하면서도 나중에 읽기 쉽도록 구조화된 형태로 변환합니다.

| 처리 항목 | 세부 내용 |
|-----------|-----------|
| 오탈자 교정 | 맞춤법, 오탈자, 잘못된 띄어쓰기 수정 |
| 문맥 정리 | 구어체를 자연스러운 문어체로 가다듬기 |
| 핵심 요약 | Bullet 형태로 핵심 내용 분류 정리 (3~5개) |
| 원문 보존 | Notion 페이지에 원본 텍스트도 함께 저장 |

#### Step 7 — Notion DB 저장

처리된 메모를 Notion Database에 저장합니다. 각 메모는 독립된 페이지로 생성되며, 프로퍼티에 메타데이터가 저장됩니다.

#### Step 8 — 피드백 메시지 발송

저장 완료 후 사용자에게 간결한 텔레그램 메시지를 발송합니다.

> **피드백 메시지 예시**
> ```
> ✅ 메모가 저장됐어요!
>
> 📁 프로젝트: Scribble
> ```

---

## 3. 프로젝트 관리

### 3.1 개념

프로젝트는 사용자가 참여하고 있는 작업·관심 영역의 단위입니다. 모든 메모는 반드시 하나의 프로젝트에 귀속됩니다. 프로젝트 목록은 사용자가 직접 추가·삭제·확인할 수 있습니다.

### 3.2 텔레그램 명령어

| 명령어 | 동작 | 응답 예시 |
|--------|------|-----------|
| `/projects` | 현재 프로젝트 목록 조회 | `📋 현재 프로젝트 (5개): Scribble, Memory Courier, ...` |
| `/add [이름]` | 새 프로젝트 추가 | `✅ 'Blog' 프로젝트가 추가됐어요!` |
| `/del [이름]` | 기존 프로젝트 삭제 | `⚠️ 'Blog'를 삭제할까요? [확인 / 취소]` |
| `/rename [구] [신]` | 프로젝트 이름 변경 | `✅ 이름이 변경됐어요!` |
| `/help` | 명령어 안내 | 사용 가능한 명령어 목록 반환 |

### 3.3 프로젝트 삭제 정책

프로젝트 삭제 시 해당 프로젝트에 속한 기존 메모는 변경되지 않으며, Notion DB에 원래 프로젝트 분류 그대로 보존됩니다. 삭제의 의미는 해당 프로젝트를 LLM 분류 대상 목록에서 제외하는 것입니다. 즉, 삭제 이후 새로 입력되는 메모는 해당 프로젝트로 분류되지 않으며, 사용자에게 프로젝트를 선택하도록 안내할 때의 목록에도 나타나지 않습니다. 과거 메모의 프로젝트 이력은 그대로 유지됩니다. 삭제 전 확인 단계(Inline keyboard로 ✅ 확인 / ❌ 취소)를 거쳐 실수를 방지합니다.

**`/rename` 정책**: 프로젝트 이름 변경 시 기존 Notion 메모의 Project 필드는 업데이트하지 않습니다. 변경 이후 신규 저장되는 메모에만 새 이름이 적용됩니다.

### 3.4 기본 프로젝트

`Uncategorized`는 시스템 예약 프로젝트로, 삭제 불가입니다. 분류에 실패하거나 사용자가 응답하지 않은 경우의 메모를 보관합니다.

### 3.5 Inline Keyboard UX 규칙

프로젝트 선택이 필요한 모든 상황에서 Telegram InlineKeyboardMarkup을 사용합니다.

| 상황 | 버튼 구성 |
|------|-----------|
| 분류 후보 5개 이하 | 후보 버튼 전체 + `Uncategorized` 버튼 |
| 분류 후보 6개 이상 | LLM 선별 상위 5개 버튼 + `Uncategorized` 버튼 + `기타 입력` 버튼 (텍스트 입력 유도) |
| `/del` 삭제 확인 | `✅ 확인` 버튼 + `❌ 취소` 버튼 |

`기타 입력` 버튼 선택 시 사용자에게 프로젝트 이름을 텍스트로 직접 입력하도록 안내합니다.

---

## 4. Notion 데이터베이스 스키마

### 4.1 Scribble Index DB

메모 목록을 관리하는 메인 데이터베이스입니다. 각 행이 하나의 메모에 해당합니다.

| 프로퍼티명 | 타입 | 설명 |
|-----------|------|------|
| Title | Title | 구조화된 메모의 첫 번째 Bullet 항목 (요약 제목) |
| Project | Select | 귀속 프로젝트 이름 |
| Tags | Multi-select | LLM이 추출한 태그 목록 (최대 5개) |
| Created At | Date | 메모 최초 생성 시각 |
| Source | Select | 입력 채널 (Telegram 고정 → 추후 확장 가능) |
| Status | Select | 처리 상태: `Processing` / `Saved` / `Error` |
| Raw Memo | Rich Text | 사용자가 입력한 원문 그대로 |
| Structured | Rich Text | LLM이 구조화한 내용 (Bullet 요약). 2000자 초과 시 잘라냄 |
| Linked Memories | Relation | Memory Courier DB와 태그 기반 연결 (향후) |

### 4.2 Project Registry DB

사용자의 프로젝트 목록을 관리하는 보조 데이터베이스입니다. **Notion DB가 단일 소스 오브 트루스**이며, 서버는 기동 시 목록을 메모리에 캐싱합니다. `/add`, `/del`, `/rename` 명령어 실행 시 Notion DB를 업데이트한 뒤 즉시 캐시를 무효화합니다.

| 프로퍼티명 | 타입 | 설명 |
|-----------|------|------|
| Name | Title | 프로젝트 이름 (유일값) |
| Description | Rich Text | 프로젝트 간략 설명 (선택) |
| Created At | Date | 프로젝트 생성일 |
| Is System | Checkbox | 시스템 예약 프로젝트 여부 (Uncategorized 등) |
| Active | Checkbox | 활성 여부 (false = 삭제됨, LLM 분류 목록에서 제외) |

---

## 5. API 및 데이터 흐름

### 5.1 Webhook 처리 엔드포인트

```
POST /webhook/telegram

1. 요청 수신 및 검증 (Telegram secret token 확인)
2. 메시지 파싱 (chat_id, user_id, text, date)
3. 라우팅 결정:
   ├─ text.startsWith('/') → 명령어 핸들러 호출
   ├─ pending_context[chat_id] 존재 → 분류 응답 처리
   └─ else → 메모 처리 파이프라인 실행
4. 즉시 HTTP 200 반환 (Telegram 재전송 방지)
5. 비동기 백그라운드 처리 (FastAPI BackgroundTasks)
```

### 5.2 메모 처리 파이프라인

| 단계 | 함수/모듈 | 핵심 동작 |
|------|-----------|-----------|
| 1. 통합 처리 | `process_memo(text, projects)` | Claude API **1회** 호출 → 분류(project + confidence) + 태그 + 구조화 결과 동시 반환 |
| 2a. 즉시 저장 (high) | `save_to_notion(memo_data)` | confidence high → Notion DB Row 저장 |
| 2b. 재질문 (medium/low) | `ask_clarification(chat_id, candidates)` | Inline keyboard로 프로젝트 선택 요청, `pending_context` 저장 |
| 3. 저장 (확인 후) | `save_to_notion(memo_data)` | 사용자 선택 수신 후 Notion DB Row 저장 |
| 4. 피드백 | `send_feedback(chat_id, result)` | 텔레그램 메시지 발송 |

### 5.3 LLM 프롬프트 설계

#### 통합 메모 처리 프롬프트 (단일 호출)

```
[System]
당신은 사용자의 개인 메모를 분석하는 어시스턴트입니다.
아래 작업을 한 번에 수행하세요:
1. 프로젝트 목록을 참고하여 메모를 가장 적합한 프로젝트로 분류
2. 메모에서 태그를 추출 (최대 5개, 소문자-하이픈 형식)
3. 메모 내용을 구조화 (제목 1줄 + 핵심 Bullet 3~5개 + 교정된 원문)

응답 형식 (JSON만 반환):
{
  "project": "<프로젝트명 또는 null>",
  "confidence": "high|medium|low",
  "candidates": ["<후보1>", "<후보2>"],  // confidence가 medium/low일 때 상위 5개 이내
  "reason": "<분류 근거 한 줄>",
  "tags": ["tag1", "tag2", "tag3"],
  "title": "<메모를 대표하는 한 줄 제목>",
  "bullets": ["<핵심1>", "<핵심2>", "<핵심3>"],
  "corrected": "<오탈자 교정 및 문맥 정리된 원문>"
}

[User]
프로젝트 목록: {projects}
메모: {memo_text}
```

---

## 6. 기술 스택

| 구성 요소 | 기술 선택 및 이유 |
|-----------|------------------|
| 사용자 인터페이스 | Telegram Bot API — 별도 앱 설치 없이 즉시 사용 가능 |
| 백엔드 프레임워크 | FastAPI (Python) — 비동기 처리, 간결한 코드, 타입 힌트 |
| 호스팅 | Railway — 간편한 배포, 자동 HTTPS, Webhook URL 고정 |
| LLM | Anthropic Claude API — 한국어 처리 우수, JSON 응답 신뢰성 높음 |
| 메인 저장소 | Notion Database API — 구조화 DB + 리치 텍스트 혼합 저장 |
| 컨텍스트 캐시 | Redis (Railway Add-on) 또는 서버 인메모리 dict (MVP) |
| 환경 변수 | Railway Env — `TELEGRAM_TOKEN`, `ANTHROPIC_KEY`, `NOTION_KEY` 등 |

---

## 7. 오류 처리

| 오류 유형 | 처리 방식 | 사용자 안내 |
|-----------|-----------|-------------|
| LLM API 오류 | 3회 재시도 후 원문만 `Uncategorized`로 저장 | `⚠️ AI 처리 중 오류가 발생했어요. 메모는 원문으로 Uncategorized에 저장됐어요.` |
| Notion API 오류 | 3회 재시도 후 실패 처리 | `❌ 저장에 실패했어요. 잠시 후 다시 시도해주세요.` |
| 분류 컨텍스트 만료 | TTL 5분 초과 시 자동 만료, `Uncategorized`로 저장 | `⏰ 응답 시간이 초과되어 'Uncategorized'로 저장했어요.` |
| Pending 충돌 (새 메모 수신) | 이전 pending 메모 자동 `Uncategorized` 저장, 새 메모 신규 처리 | `이전 메모가 Uncategorized로 저장됐어요.` (새 메모 처리 계속) |
| 중복 메시지 | Telegram `update_id` 기반 중복 제거 | (내부 처리, 사용자에게 노출 없음) |
| 빈 메모 | 텍스트 길이 검증 | `💬 메모 내용을 입력해주세요.` |

---

## 8. 타 서비스 연동

### 8.1 Memory Courier · People Keeper 연동

Scribble, Memory Courier, People Keeper 세 서비스는 공통 태그 스키마를 공유합니다. 동일한 태그가 여러 서비스의 항목에 붙어 있을 경우, 추후 구현될 대시보드에서 시각적으로 연결하여 탐색할 수 있습니다.

| 서비스 | 연동 방식 |
|--------|-----------|
| Memory Courier | 태그 기반 Notion Relation 연결. 같은 태그를 가진 메모와 복기 카드를 대시보드에서 함께 탐색 |
| People Keeper | 인물 이름이 태그로 추출된 경우, People Keeper의 해당 인물 페이지와 Relation 연결 (향후 구현) |

### 8.2 향후 확장 가능성

- **웹/데스크톱 캡처** — 브라우저 확장으로 URL·스크린샷을 Scribble로 전송
- **음성 메모** — Telegram 음성 메시지 → Whisper STT → 텍스트 변환 후 동일 파이프라인
- **대시보드** — 태그·프로젝트 기반 메모 시각화 (Notion Linked Database 또는 별도 웹)
- **정기 요약** — 주간/월간 단위로 특정 프로젝트 메모를 요약하여 텔레그램 전송

---

## 9. 개발 로드맵

| 단계 | 기간 | 주요 목표 |
|------|------|-----------|
| Phase 1 — MVP | 2~3주 | 텔레그램 Webhook 수신 → 프로젝트 분류 → Notion 저장 → 피드백 메시지. `/projects`, `/add`, `/del` 명령어. |
| Phase 2 — 안정화 | 2주 | 오류 처리 강화, Redis 컨텍스트 캐시 도입, 분류 재질문 UX 개선, 태그 자동 완성. |
| Phase 3 — 연동 | 3~4주 | Memory Courier·People Keeper 태그 Relation 연결, 대시보드 기획 및 프로토타이핑. |

---

## 10. 보안 원칙

- 모든 API 키 및 토큰은 Railway 환경 변수로 관리, 코드에 하드코딩 금지
- Telegram Webhook 요청은 `secret_token` 헤더로 진위 검증
- Notion API 토큰은 Integration 단위로 최소 권한 부여
- 사용자 메모는 본인 Notion Workspace에만 저장 (서버 영구 저장 없음)
- 서버 인메모리 캐시의 컨텍스트 데이터는 TTL 5분 후 자동 소멸

---

## 11. 미결 항목 (추후 반영)

| 항목 | 내용 |
|------|------|
| 태그 언어 및 크로스서비스 구조 | Memory Courier / People Keeper Notion DB 문서 분석 후 태그 언어(한국어/영어), 네임스페이스 규칙 확정 및 설계서 반영 예정 |

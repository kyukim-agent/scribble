import json
import anthropic
from typing import Optional
from config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_SYSTEM_PROMPT = """당신은 사용자의 개인 메모를 분석하는 어시스턴트입니다.
아래 작업을 한 번에 수행하세요:
1. 프로젝트 목록을 참고하여 메모를 가장 적합한 프로젝트로 분류
2. 메모에서 태그를 추출 (최대 5개)
3. 메모 내용을 구조화 (제목 1줄 + 핵심 Bullet 3~5개 + 교정된 원문)

태그 언어 규칙:
- 한국어 개념·주제는 한국어로 (예: 가격경쟁, 조직이동)
- 영어 고유명사·브랜드는 영어 원어로 (예: BCG, SAP, M&A)

confidence 기준:
- high: 프로젝트 목록 중 명확히 일치하는 항목이 있음
- medium: 관련 있어 보이는 후보가 2~3개 존재
- low: 분류 불가 또는 여러 후보가 비슷한 수준

응답 형식 (JSON만 반환, 다른 텍스트 없이):
{
  "project": "<프로젝트명 또는 null>",
  "confidence": "high|medium|low",
  "candidates": ["<후보1>", "<후보2>"],
  "reason": "<분류 근거 한 줄>",
  "tags": ["tag1", "tag2"],
  "title": "<메모를 대표하는 한 줄 제목>",
  "bullets": ["<핵심1>", "<핵심2>", "<핵심3>"],
  "corrected": "<오탈자 교정 및 문맥 정리된 원문>"
}"""


async def process_memo(text: str, projects: list[str]) -> Optional[dict]:
    projects_str = ", ".join(projects) if projects else "없음"
    user_msg = f"프로젝트 목록: {projects_str}\n\n메모: {text}"

    for attempt in range(3):
        try:
            response = await _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception:
            if attempt == 2:
                return None
    return None

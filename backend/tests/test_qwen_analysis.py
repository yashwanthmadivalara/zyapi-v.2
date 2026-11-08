import asyncio

import pytest

from app import services


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise services.httpx.HTTPStatusError("failure", request=None, response=self)

    def json(self):
        return {"message": {"content": self.content}}


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.prompts = []
        self.index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, **kwargs):
        self.prompts.append(json["messages"][1]["content"])
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return response


def valid_response():
    return FakeResponse('{"moments":[{"start_seconds":0,"end_seconds":20,"suggested_title":"A","opening_hook":"Hook","explanation":"Self-contained explanation","content_category":"education","suggested_caption":"Caption","quality_score":8}]}')


def test_analysis_accepts_wrapped_response_and_retries_with_changed_prompt(monkeypatch):
    client = FakeClient([FakeResponse('{"moments":[{"start_seconds":80}]}'), valid_response()])
    monkeypatch.setattr(services.httpx, "AsyncClient", lambda **kwargs: client)
    segments = [{"start": 0, "end": 12, "text": "First thought"}, {"start": 12, "end": 24, "text": "Second thought"}]
    result = asyncio.run(services.analyze_transcript_with_ollama(segments, 30, retries=1))
    assert result[0]["start_seconds"] == 0
    assert len(client.prompts) == 2
    assert client.prompts[0] != client.prompts[1]


def test_analysis_splits_long_transcript_and_preserves_timestamps(monkeypatch):
    client = FakeClient([valid_response()])
    monkeypatch.setattr(services.httpx, "AsyncClient", lambda **kwargs: client)
    segments = [{"start": i * 12, "end": (i + 1) * 12, "text": "x" * 3000} for i in range(6)]
    result = asyncio.run(services.analyze_transcript_with_ollama(segments, 72, retries=0))
    assert result
    assert len(client.prompts) >= 2
    assert all(0 <= item["start_seconds"] < item["end_seconds"] <= 72 for item in result)


def test_analysis_reports_no_usable_moments(monkeypatch):
    client = FakeClient([FakeResponse('{"moments": []}')])
    monkeypatch.setattr(services.httpx, "AsyncClient", lambda **kwargs: client)
    with pytest.raises(RuntimeError, match="no valid moments"):
        asyncio.run(services.analyze_transcript_with_ollama([{"start": 0, "end": 20, "text": "Text"}], 30, retries=0))

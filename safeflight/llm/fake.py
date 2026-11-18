"""Test doubles so CI never calls the API or needs a key.

- `FakeLLM` plays back a fixed script of responses, in order.
- `ReplayLLM` plays back recorded responses keyed by a hash of the request messages.
  In record mode it calls a real LLM and saves what it returns.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from crewai import BaseLLM
from pydantic import Field, PrivateAttr


def _text_of(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    return json.dumps(messages, sort_keys=True, default=str)


class FakeLLM(BaseLLM):
    """Returns `script[i]` on call i; the last entry repeats once the script runs out."""

    model: str = "fake"
    script: list[str] = Field(default_factory=list)
    _calls: list[Any] = PrivateAttr(default_factory=list)

    def __init__(self, **data: Any) -> None:
        data.setdefault("model", "fake")  # BaseLLM requires an explicit model name
        super().__init__(**data)

    def call(  # type: ignore[override]
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> str:
        self._calls.append(messages)
        if not self.script:
            raise RuntimeError("FakeLLM has an empty script")
        return self.script[min(len(self._calls), len(self.script)) - 1]

    @property
    def calls(self) -> list[Any]:
        return self._calls

    def supports_function_calling(self) -> bool:
        return False


class MissingRecording(KeyError):
    pass


class ReplayLLM(BaseLLM):
    """Replays responses from a JSON file. Set `record_with` to capture new ones."""

    model: str = "replay"
    path: Path
    record_with: Any = None  # a real BaseLLM, only when recording
    _store: dict[str, str] = PrivateAttr(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        data.setdefault("model", "replay")
        super().__init__(**data)

    def model_post_init(self, __context: Any) -> None:
        if self.path.exists():
            self._store = json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def key(messages: Any) -> str:
        return hashlib.sha256(_text_of(messages).encode()).hexdigest()[:16]

    def call(  # type: ignore[override]
        self,
        messages: Any,
        tools: Any = None,
        callbacks: Any = None,
        available_functions: Any = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: Any = None,
    ) -> str:
        k = self.key(messages)
        if k in self._store:
            return self._store[k]
        if self.record_with is None:
            raise MissingRecording(f"no recording for request {k} in {self.path}")
        out = self.record_with.call(messages, tools, callbacks, available_functions, from_task, from_agent)
        self._store[k] = str(out)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._store, indent=2, sort_keys=True), encoding="utf-8")
        return self._store[k]

    def supports_function_calling(self) -> bool:
        return False

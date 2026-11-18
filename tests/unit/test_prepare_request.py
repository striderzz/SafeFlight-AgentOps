from safeflight.llm.claude import FALLBACK_BETA, STRUCTURED_OUTPUTS_BETA, prepare_request

BASE = {"model": "claude-haiku-5-5", "max_tokens": 1000, "messages": [{"role": "user", "content": "hi"}]}


def test_sets_effort_and_prompt_caching():
    p = prepare_request(BASE, model="claude-haiku-5-5", effort="low")
    assert p["output_config"] == {"effort": "low"}
    assert p["cache_control"] == {"type": "ephemeral"}
    assert "betas" not in p and "extra_body" not in p


def test_removes_sampling_parameters():
    p = prepare_request(
        {**BASE, "temperature": 0.2, "top_p": 0.9, "top_k": 5}, model="claude-haiku-5-5", effort="low"
    )
    assert not {"temperature", "top_p", "top_k"} & p.keys()


def test_moves_deprecated_output_format_to_output_config():
    schema = {"type": "json_schema", "schema": {"type": "object"}}
    p = prepare_request(
        {**BASE, "betas": [STRUCTURED_OUTPUTS_BETA], "extra_body": {"output_format": schema}},
        model="claude-haiku-5-5",
        effort="medium",
    )
    assert p["output_config"] == {"effort": "medium", "format": schema}
    assert "betas" not in p  # nothing beta left, so the GA endpoint is used
    assert "extra_body" not in p


def test_relaxes_forced_tool_choice():
    for forced in ({"type": "any"}, {"type": "tool", "name": "x"}):
        p = prepare_request({**BASE, "tool_choice": forced}, model="claude-opus-5-5", effort="medium")
        assert p["tool_choice"] == {"type": "auto"}
    kept = prepare_request({**BASE, "tool_choice": {"type": "none"}}, model="claude-haiku-5-5", effort="low")
    assert kept["tool_choice"] == {"type": "none"}


def test_opus_gets_server_side_refusal_fallback():
    p = prepare_request(BASE, model="claude-opus-5-5", effort="high")
    assert p["betas"] == [FALLBACK_BETA]
    assert p["extra_body"] == {"fallbacks": "default"}


def test_does_not_mutate_the_input():
    params = {**BASE, "temperature": 0.5}
    prepare_request(params, model="claude-haiku-5-5", effort="low")
    assert params["temperature"] == 0.5 and "output_config" not in params

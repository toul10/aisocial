"""AI providers with fake SDK clients: request shapes and error handling."""

import base64
from types import SimpleNamespace

import anthropic
import httpx2
import openai
import pytest
from helpers import JPEG, Recorder

from aisocial.ai import AIError, AIService
from aisocial.ai.anthropic_provider import FALLBACK_BETA, AnthropicText
from aisocial.ai.openai_provider import OpenAIImages, OpenAIText
from aisocial.ai.prompts import clean_output, parse_lines, post_prompt


def claude_response(text="Γεια", stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])


def claude_client(result):
    return SimpleNamespace(
        messages=SimpleNamespace(create=Recorder(result)),
        beta=SimpleNamespace(messages=SimpleNamespace(create=Recorder(result))),
        models=SimpleNamespace(retrieve=Recorder(SimpleNamespace(id="claude-opus-5-5"))),
    )


def test_claude_request_uses_effort_and_server_side_fallback():
    client = claude_client(claude_response(" Καλημέρα! "))
    assert AnthropicText("k", "claude-opus-5-5", "low", client=client).complete("SYS", "PROMPT") == "Καλημέρα!"
    assert client.beta.messages.create.kwargs == {
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
        "model": "claude-opus-5-5",
        "max_tokens": 16000,
        "system": "SYS",
        "messages": [{"role": "user", "content": "PROMPT"}],
        "output_config": {"effort": "low"},
    }
    assert client.messages.create.kwargs is None


def test_claude_sonnet_5_5_also_uses_fallback():
    client = claude_client(claude_response())
    AnthropicText("k", "claude-sonnet-5-5", "medium", client=client).complete("S", "P")
    assert client.beta.messages.create.kwargs["output_config"] == {"effort": "medium"}


def test_older_claude_model_gets_a_plain_request():
    client = claude_client(claude_response())
    AnthropicText("k", "claude-haiku-4-5", "low", client=client).complete("S", "P")
    kwargs = client.messages.create.kwargs
    assert "output_config" not in kwargs and "betas" not in kwargs and "temperature" not in kwargs


@pytest.mark.parametrize("text,stop", [("x", "refusal"), ("x", "max_tokens"), ("   ", "end_turn")])
def test_claude_unusable_answers_raise(text, stop):
    client = claude_client(claude_response(text, stop))
    with pytest.raises(AIError):
        AnthropicText("k", "claude-opus-5-5", client=client).complete("S", "P")


def test_claude_errors_are_translated():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    bad_key = anthropic.AuthenticationError("invalid x-api-key", response=httpx2.Response(401, request=request), body=None)
    with pytest.raises(AIError, match="API key"):
        AnthropicText("k", "claude-opus-5-5", client=claude_client(bad_key)).complete("S", "P")
    offline = anthropic.APIConnectionError(request=request)
    with pytest.raises(AIError, match="No connection"):
        AnthropicText("k", "claude-opus-5-5", client=claude_client(offline)).complete("S", "P")


def test_claude_verify_looks_up_the_model():
    client = claude_client(claude_response())
    assert AnthropicText("k", "claude-opus-5-5", client=client).verify() == "Claude OK (claude-opus-5-5)"
    assert client.models.retrieve.args == ("claude-opus-5-5",)


def test_openai_text_uses_responses_api():
    create = Recorder(SimpleNamespace(output_text=" Καλημέρα "))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert OpenAIText("k", "gpt-5-mini", client=client).complete("SYS", "P") == "Καλημέρα"
    assert create.kwargs == {"model": "gpt-5-mini", "instructions": "SYS", "input": "P"}


def test_openai_image_is_jpeg_from_base64():
    generate = Recorder(SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(JPEG).decode(), url=None)]))
    client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    assert OpenAIImages("k", "gpt-image-1", client=client).generate("bread") == JPEG
    assert generate.kwargs == {"model": "gpt-image-1", "prompt": "bread", "size": "1024x1024", "output_format": "jpeg"}


def test_openai_image_permission_error_mentions_verification():
    request = httpx2.Request("POST", "https://api.openai.com/v1/images/generations")
    denied = openai.PermissionDeniedError("organization must be verified", response=httpx2.Response(403, request=request), body=None)
    client = SimpleNamespace(images=SimpleNamespace(generate=Recorder(denied)))
    with pytest.raises(AIError, match="Organization verification"):
        OpenAIImages("k", "gpt-image-1", client=client).generate("x")


def test_provider_choice(settings):
    keys, preference = {}, ["auto"]
    service = AIService(settings, stored_key=lambda name: keys.get(name, ""), stored_provider=lambda: preference[0])
    assert service.text_choice() is None
    with pytest.raises(AIError, match="AI key"):
        service.text()
    keys["openai_api_key"] = "sk-test-openai"
    assert service.text_choice() == "openai"
    keys["anthropic_api_key"] = "sk-ant-test"
    assert service.text_choice() == "anthropic"
    preference[0] = "openai"
    assert service.text_choice() == "openai"
    del keys["openai_api_key"]
    assert service.text_choice() is None
    with pytest.raises(AIError, match="OpenAI"):
        service.text()


def test_clean_output():
    assert clean_output('  "Γεια!"  ') == "Γεια!"
    assert clean_output("«Καλημέρα»") == "Καλημέρα"
    assert clean_output('"Hi" she said "bye"') == '"Hi" she said "bye"'


def test_parse_lines():
    assert parse_lines("1. Ένα\n2) Δύο\n- ένα\n\n• Τρία\n", 10) == ["Ένα", "Δύο", "Τρία"]
    assert parse_lines("a\nb\nc", 2) == ["a", "b"]


def test_post_prompt_language_and_platform():
    prompt = post_prompt(topic="Καφές", platform="linkedin", target=900, limit=3000, content={"language": ""})
    assert "same language as the topic" in prompt and "LinkedIn" in prompt and "900" in prompt
    prompt = post_prompt(topic="Coffee", platform="x", target=140, limit=280, content={"language": "English"})
    assert "Write in English." in prompt

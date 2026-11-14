import pytest
from helpers import ANTHROPIC_KEY, JPEG, OPENAI_KEY, FakeImages, FakeText

from aisocial.ai import AIService


@pytest.fixture
def fake_text(monkeypatch, client):
    fake = FakeText()
    monkeypatch.setattr(AIService, "_make_text", lambda self, provider, key: fake)
    client.put("/api/ai", json={"anthropic_api_key": ANTHROPIC_KEY})
    return fake


def test_without_key_the_error_says_what_to_do(client):
    resp = client.post("/api/generate/text", json={"platform": "x", "topic": "Καφές"})
    assert resp.status_code == 400
    assert "AI key" in resp.get_json()["error"]


def test_post_uses_brand_topic_and_instructions(client, fake_text):
    client.put("/api/content", json={"brand_name": "Φούρνος Νίκος", "about": "Προζυμένιο ψωμί", "language": "Ελληνικά"})
    fake_text.replies = ['"Φρέσκο ψωμί κάθε πρωί! Εσύ τι προτιμάς;"']
    resp = client.post("/api/generate/text", json={
        "platform": "x", "topic": "Πρωινό", "length": "short", "instructions": "Κλείσε με ερώτηση",
    })
    draft = resp.get_json()["draft"]
    assert draft["text"] == "Φρέσκο ψωμί κάθε πρωί! Εσύ τι προτιμάς;"  # wrapping quotes removed
    assert (draft["limit"], draft["target"], draft["over_limit"], draft["platform"]) == (280, 140, False, "x")
    system, prompt = fake_text.calls[0]
    assert "Φούρνος Νίκος" in system and "Προζυμένιο ψωμί" in system
    assert "Topic: Πρωινό" in prompt and "Κλείσε με ερώτηση" in prompt
    assert "X (Twitter)" in prompt and "Write in Ελληνικά." in prompt


def test_too_long_post_is_shortened_once(client, fake_text):
    fake_text.replies = ["α" * 400, "β" * 200]
    draft = client.post("/api/generate/text", json={"platform": "x", "topic": "Θέμα"}).get_json()["draft"]
    assert draft["shortened"] is True and draft["text"] == "β" * 200
    assert len(fake_text.calls) == 2 and "400 characters" in fake_text.calls[1][1]


def test_still_too_long_is_flagged(client, fake_text):
    fake_text.replies = ["α" * 400, "β" * 300]
    draft = client.post("/api/generate/text", json={"platform": "x", "topic": "Θέμα"}).get_json()["draft"]
    assert draft["over_limit"] is True and draft["count"] == 300


def test_blank_topic_picks_an_active_topic(client, fake_text):
    titles = [t["title"] for t in client.get("/api/state").get_json()["topics"]]
    draft = client.post("/api/generate/text", json={"platform": "linkedin"}).get_json()["draft"]
    assert draft["topic"] in titles


def test_blank_topic_without_topics(client, fake_text):
    for topic in client.get("/api/state").get_json()["topics"]:
        client.delete(f"/api/topics/{topic['id']}")
    resp = client.post("/api/generate/text", json={"platform": "x"})
    assert resp.status_code == 400 and "topic" in resp.get_json()["error"]


def test_bad_platform_or_length(client, fake_text):
    assert client.post("/api/generate/text", json={"platform": "myspace", "topic": "a"}).status_code == 400
    assert client.post("/api/generate/text", json={"platform": "x", "topic": "a", "length": "huge"}).status_code == 400


def test_suggested_topics_skip_existing(client, fake_text):
    existing = client.get("/api/state").get_json()["topics"][0]["title"]
    fake_text.replies = [f"1. Νέο θέμα ένα\n- {existing}\n• Νέο θέμα δύο\nΝέο θέμα ένα\n"]
    topics = client.post("/api/generate/topics", json={"count": 5}).get_json()["topics"]
    assert topics == ["Νέο θέμα ένα", "Νέο θέμα δύο"]
    assert client.post("/api/generate/topics", json={"count": 99}).status_code == 400


def test_image_prompt(client, fake_text):
    fake_text.replies = ["Warm bread on a wooden counter, morning light"]
    resp = client.post("/api/generate/image-prompt", json={"text": "Φρέσκο ψωμί"})
    assert resp.get_json()["prompt"] == "Warm bread on a wooden counter, morning light"
    assert "Φρέσκο ψωμί" in fake_text.calls[0][1]


def test_image_needs_openai_key(client, fake_text):
    resp = client.post("/api/generate/image", json={"prompt": "ψωμί"})
    assert resp.status_code == 400 and "OpenAI" in resp.get_json()["error"]


def test_generated_image_is_saved_and_served(client, monkeypatch):
    fake_images = FakeImages(JPEG)
    monkeypatch.setattr(AIService, "_make_images", lambda self, key: fake_images)
    client.put("/api/ai", json={"openai_api_key": OPENAI_KEY})
    image = client.post("/api/generate/image", json={"prompt": "Ψωμί σε πάγκο"}).get_json()["image"]
    assert image["id"].endswith(".jpg")
    assert fake_images.prompts[0].startswith("Ψωμί σε πάγκο") and "No text" in fake_images.prompts[0]
    served = client.get(image["url"])
    assert served.status_code == 200 and served.mimetype == "image/jpeg" and served.data == JPEG

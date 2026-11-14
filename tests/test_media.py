import io

import pytest
from helpers import JPEG, PNG

from aisocial import media


def multipart(data, name="file.bin"):
    return {"data": {"file": (io.BytesIO(data), name)}, "content_type": "multipart/form-data"}


def test_sniff():
    assert media.sniff(PNG) == "png"
    assert media.sniff(JPEG) == "jpg"
    assert media.sniff(b"GIF89a" + b"\x00" * 10) == "gif"
    with pytest.raises(media.MediaError):
        media.sniff(b"<svg xmlns='http://www.w3.org/2000/svg'/>")


def test_save_and_load(tmp_path):
    image_id = media.save_image(tmp_path, PNG)
    assert media.IMAGE_ID_RE.match(image_id)
    image = media.load_image(tmp_path, image_id)
    assert (image.data, image.mime, image.filename) == (PNG, "image/png", "image.png")


def test_size_limits(tmp_path):
    with pytest.raises(media.MediaError):
        media.save_image(tmp_path, b"")
    with pytest.raises(media.MediaError):
        media.save_image(tmp_path, PNG + b"\x00" * media.MAX_IMAGE_BYTES)


def test_image_path_rejects_anything_but_generated_names(tmp_path):
    (tmp_path / "secret.png").write_bytes(PNG)
    assert media.image_path(tmp_path, "../secret.png") is None
    assert media.image_path(tmp_path, "secret.png") is None
    assert media.image_path(tmp_path, "0" * 32 + ".png") is None  # valid name, no such file


def test_upload_endpoint(client):
    ok = client.post("/api/images", **multipart(JPEG, "photo.jpg"))
    assert ok.status_code == 201
    assert client.get(ok.get_json()["image"]["url"]).data == JPEG

    bad = client.post("/api/images", **multipart(b"hello", "notes.txt"))
    assert bad.status_code == 400 and "PNG" in bad.get_json()["error"]
    assert client.post("/api/images", data={}, content_type="multipart/form-data").status_code == 400

    too_big = client.post("/api/images", **multipart(PNG + b"\x00" * (6 * 1024 * 1024), "big.png"))
    assert too_big.status_code == 400 and "5 MB" in too_big.get_json()["error"]
    huge = client.post("/api/images", **multipart(PNG + b"\x00" * (9 * 1024 * 1024), "huge.png"))
    assert huge.status_code == 413 and huge.get_json()["ok"] is False


def test_media_route_only_serves_saved_images(client):
    assert client.get("/media/../../etc/passwd").status_code == 404
    assert client.get("/media/" + "0" * 32 + ".png").status_code == 404

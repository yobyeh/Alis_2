from app.status import StatusProvider


def test_footer_contains_ip_and_port(monkeypatch):
    settings = {"system": {}}
    sp = StatusProvider(settings, web_port=1234)
    monkeypatch.setattr(sp, "_get_local_ip", lambda: "10.0.0.5")
    snap = sp.snapshot()
    assert snap["footer"] == "http://10.0.0.5:1234"

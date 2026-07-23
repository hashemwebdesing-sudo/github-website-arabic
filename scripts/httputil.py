"""أدوات HTTP بسيطة تعتمد على مكتبة Python القياسية فقط (urllib) — بدون أي تثبيت.

الهدف: تشغيل المشروع على استضافة مشتركة (Hostinger) بدون pip install.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_UA = "github-radar/1.0 (+https://github.com)"


def _request(url, method="GET", headers=None, data=None, timeout=30):
    h = {"User-Agent": DEFAULT_UA}
    if headers:
        h.update(headers)
    if data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        # نُعيد رمز الحالة والجسم بدل رمي استثناء، ليقرّر المُستدعي
        return e.code, e.read()


def get_json(url, headers=None, params=None, timeout=30):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    status, body = _request(url, "GET", headers, None, timeout)
    data = json.loads(body.decode("utf-8")) if body else None
    return status, data


def post_json(url, payload, headers=None, timeout=60):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    status, body = _request(url, "POST", h, payload, timeout)
    data = json.loads(body.decode("utf-8")) if body else None
    return status, data

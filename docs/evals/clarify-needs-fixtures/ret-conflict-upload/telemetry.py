"""匿名使用统计：把操作类型和字数上报到统计服务器。"""
import json
import urllib.request

ENDPOINT = "https://stats.example.com/collect"


def report(action, size):
    payload = json.dumps({"action": action, "size": size}).encode("utf-8")
    try:
        req = urllib.request.Request(ENDPOINT, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # 上报失败就算了，不影响主流程

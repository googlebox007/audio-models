"""stub: 让 matcha/diffusers 的 huggingface_hub import 链在 CosyVoice 本地模型下通。
补齐 diffusers 需要的但旧版 huggingface_hub 没有的符号。"""
import huggingface_hub as _hf
import huggingface_hub.errors as _hfe
try:
    import huggingface_hub.utils as _hfu
except ImportError:
    _hfu = None

class _FakeExc(Exception):
    pass

for _name in ("resolve_revision",):
    if not hasattr(_hf, _name):
        setattr(_hf, _name, lambda *a, **k: None)

for _name in ("RevisionResolutionError",):
    if not hasattr(_hfe, _name):
        setattr(_hfe, _name, type(_name, (_FakeExc,), {}))
    if not hasattr(_hf, _name):
        setattr(_hf, _name, getattr(_hfe, _name))

if _hfu is not None:
    for _name in ("httpx",):
        if not hasattr(_hfu, _name):
            try:
                import httpx
                _hfu.httpx = httpx
            except ImportError:
                _hfu.httpx = None

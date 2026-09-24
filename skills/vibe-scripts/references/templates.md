# vibe-scripts 模板

新写脚本、或要调整脚本结构（升级、拆包、收口变化轴）时才读本文件。规则在 SKILL.md，这里只放照着抄的样子。

## 标准级：单文件四层五区

依赖方向固定：**App → Core → Port ← Adapter**。Core 永不知道 Adapter 的存在。

```python
# 结构: vibe-scripts/standard
# 用途: <一句话>
# 用法: py -3 xxx.py parse log.txt
# 原始需求: <生成本脚本时的需求描述原文，供未来重生成/大改时使用>

# ===== 1 配置/常量 =====
DEFAULT_BAUD = 9600

# ===== 2 Port：接口定义（只有一种 IO 实现时省掉本区，Core 直接收数据）=====
class Transport:                      # 或 typing.Protocol
    def transact(self, frame: bytes) -> bytes: raise NotImplementedError

# ===== 3 Core：纯逻辑（只调 Port；禁止 open/serial/socket/print）=====
def decode_frame(frame: bytes) -> dict: ...

# ===== 4 Adapter：实现 + 注册（示例是“真实串口 / 仿真”两种正式运行方式）=====
class SerialTransport(Transport): ...
class SimTransport(Transport):        # 仿真是正式运行方式，走注册表，不是 if 分支
    def __init__(self, replyfile): ...
TRANSPORTS = {"serial": SerialTransport, "sim": SimTransport}

# ===== 5 App：命令表 + CLI 入口（调度组合、负责打印）=====
def cmd_send(args):
    tp = TRANSPORTS[args.transport](...)   # 传输选择只发生在这一行
    ...
COMMANDS = {"parse": cmd_parse, "send": cmd_send}
```

只有一种 IO 实现时：删掉第 2 区，第 4 区写普通函数（如 `read_frames(path)`），第 5 区直接调它、把数据喂给 Core。

## 工具包级：一条变化轴的注册表

成员各自依赖第三方库、设备、网络时，用下面的惰性加载写法，一个成员导入失败不影响注册表本身：

```python
# adapters/platforms/__init__.py —— 这条轴唯一的名单；只登记名字，不在这里导入成员
import importlib
PLATFORMS = ("alpha", "beta")

def load(name):
    return importlib.import_module(f"{__name__}.{name}")

def load_all():
    ok, bad = {}, {}
    for name in PLATFORMS:
        try:
            ok[name] = load(name)
        except Exception as e:          # 一个成员导入失败只标它自己
            bad[name] = repr(e)
    return ok, bad

# adapters/platforms/alpha.py —— 成员的一切都在这一个文件里
CAPS = {"views", "links"}          # 能力由成员自己声明
def check(ctx) -> list[str]: ...  # 返回问题列表，不抛到上层
```

成员只是几个纯函数时，一张 dict 就够：`FORMATS = {"csv": to_csv, "json": to_json}`。

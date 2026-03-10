---
name: raccoon-dataanalysis
description: 当用户需要使用小浣熊(Raccoon)进行数据分析、代码解释器会话管理、文件上传下载、数据可视化、办公解释器交互时使用此技能。触发词包括"小浣熊数据分析"、"Raccoon数据分析"、"代码解释器"、"办公解释器"、"数据分析会话"。
---

# 小浣熊数据分析 SKILL

你是小浣熊(Raccoon)办公解释器的操作助手。你的职责是通过调用小浣熊远程 API 或者本技能相关脚本来完成用户的数据分析需求。

## !! 最高优先级行为规则 !!

**你必须严格遵守以下规则，不得违反：**

1. **禁止本地分析数据。** 不要用 Read 工具读取用户的数据文件内容，不要用 Python/openpyxl/pandas/matplotlib 等在本地分析数据或画图。你不是本地数据分析工具。
2. **所有数据分析工作必须交给小浣熊远程 API 完成。** 你的角色是：把用户的文件上传到小浣熊 → 把用户的需求发给小浣熊 → 把小浣熊返回的结果展示给用户。
3. **Skill 加载后立即开始工作。** 不要说"技能无法启动"、"似乎无法连接"之类的话。直接检查环境变量，然后执行 API 调用。
4. **使用本 SKILL 提供的 Python 脚本调用 API。** 不要自己写 curl 命令或自己从零写 Python 代码调 API。直接运行 `scripts/` 下的现成脚本。

## Skill 加载后的标准动作

当本 SKILL 被加载后，按以下步骤执行（不要跳过任何一步）：

**步骤 1** — 检查环境变量：
```bash
echo "RACCOON_API_HOST=${RACCOON_API_HOST:-未设置}" && echo "RACCOON_API_TOKEN=${RACCOON_API_TOKEN:+已设置(${#RACCOON_API_TOKEN}字符)}"
```

**步骤 2** — 如果环境变量缺失，向用户索要：
```
请设置以下环境变量后重试：
export RACCOON_API_HOST="https://code.xiaohuanxiong.com"
export RACCOON_API_TOKEN="your-api-token"
```

**步骤 3** — 环境变量就绪后，根据用户需求直接执行对应的工作流。

## 确定脚本路径

本 SKILL 的脚本位于 SKILL.md 同级的 `scripts/` 目录下。加载后先确定绝对路径：

```bash
# SKILL_DIR 是 SKILL.md 所在目录，需要根据实际安装位置确定
# 常见位置示例：
ls .claude/skills/raccoon-data-analysis-skill/scripts/ 2>/dev/null
find ~ -path "*/raccoon-data-analysis-skill/scripts/main.py" -maxdepth 6 2>/dev/null | head -1
```

确定路径后，后续命令中使用绝对路径。例如：
```bash
SKILL_DIR="/actual/path/to/raccoon-data-analysis-skill"
python3 "$SKILL_DIR/scripts/main.py" analyze --file data.xlsx --prompt "分析数据"
```

## 工作流

### 流程一：用户提供了文件要分析（最常见场景）

当用户说"分析这个文件"、"画个图"、"帮我看看这个 Excel"时：

```bash
python3 "$SKILL_DIR/scripts/main.py" analyze \
  --file "/absolute/path/to/用户的文件.xlsx" \
  --prompt "用户的具体分析需求" \
  --output ./output
```

**注意：`--file` 参数必须使用用户文件的绝对路径。**

这一条命令会自动完成全部流程：创建会话 → 上传文件到小浣熊 → 发起对话 → 流式接收结果 → 下载生成物到本地。

### 流程二：纯对话（无文件）

当用户只是要求计算、编程、生成数据时：

```bash
python3 "$SKILL_DIR/scripts/main.py" analyze \
  --prompt "用Python计算1到100的素数之和"
```

### 流程三：需要精细控制（多轮对话、分步操作）

```bash
python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR/scripts')
from main import RaccoonClient

client = RaccoonClient()

# 创建会话
session = client.create_session('我的分析')
sid = session['id']
print(f'会话ID: {sid}')

# 上传文件
file_id = client.upload_temp_file('/absolute/path/to/file.xlsx')
print(f'文件ID: {file_id}')

# 第一轮对话
result = client.chat(sid, '分析数据趋势', upload_file_ids=[file_id])

# 第二轮对话（追问）
result2 = client.chat(sid, '请用饼图展示占比')

# 下载生成物
downloaded = client.download_artifacts(sid, output_dir='./output')
for p in downloaded:
    print(f'已下载: {p}')
"
```

### 流程四：查询已有会话

```bash
python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR/scripts')
from main import RaccoonClient
client = RaccoonClient()
for s in client.list_sessions()[:10]:
    print(f\"{s['id']} | {s.get('title', '无标题')}\")
"
```

## 完整的示例对话

### 示例：用户上传 Excel 让小浣熊画雷达图

**用户**: @雷达图测试数据.xlsx 请绘制雷达图，展示学生心理状态各维度数据

**助手的正确行为**（你必须这样做）：

1. 不要读取 xlsx 文件内容
2. 不要本地安装 matplotlib
3. 直接调用小浣熊 API：

```bash
# 先确认环境
echo "RACCOON_API_HOST=${RACCOON_API_HOST:-未设置}" && echo "RACCOON_API_TOKEN=${RACCOON_API_TOKEN:+已设置}"

# 调用小浣熊分析（文件上传到远程，远程执行代码画图）
python3 "$SKILL_DIR/scripts/main.py" analyze \
  --file "/absolute/path/to/雷达图测试数据.xlsx" \
  --prompt "这张表格为某县学生心理状态测评的各维度数据，请绘制雷达图，展示各维度数值，包括某县水平、平均值、标准差" \
  --output ./output \
  --show-code
```

4. 脚本会自动完成所有步骤并下载生成的雷达图到 `./output/`
5. 将下载的图片路径告知用户，或用 `open` 命令打开

**助手的错误行为**（你绝对不能这样做）：
- ~~用 Read 工具读取 xlsx~~
- ~~用 `python3 -c "import openpyxl..."` 本地解析 Excel~~
- ~~用 `pip3 install matplotlib` 然后本地画图~~
- ~~说"技能无法启动"或"无法连接到办公解释器"~~

## 生成物展示

分析完成后，生成物（图片/文件）会下载到 `--output` 目录。展示给用户：

```bash
# macOS 打开图片
open ./output/chart.png

# 或列出所有生成物
ls -la ./output/
```

## 错误处理

### 业务错误码

| 错误码 | 含义 | 处理建议 |
|--------|------|---------|
| 100012 | 会话ID不存在 | 重新创建会话 |
| 100015 | 会话沙盒资源不足 | 删除旧会话后重试 |
| 100016/100017 | 文件数量/大小超限 | 减少文件 |
| 100023 | 文件不存在 | 确认文件路径 |
| 200103 | 请求速率超限 | 等待后重试（脚本自动重试） |
| 200506 | 当日问题超限 | 次日再试 |
| 300001 | 模型不存在 | 检查 model 参数 |

### 沙盒运行时错误

| 错误 | 处理 |
|------|------|
| `context canceled` | 等待 5-10s 后重试，反复出现则删除会话重建 |
| 执行超时 | 简化任务拆分对话 |
| `MemoryError` | 减小数据量 |
| SSE 中途断开 | 通过 messages 接口查询已有结果 |

脚本已内置自动重试（3次，间隔 5/10/20s）。

### 认证错误

| HTTP 状态 | 处理 |
|-----------|------|
| 401 | Token 无效或过期，向用户索要新 Token |
| 429 | 速率超限，等待后重试 |

## SSE 流式响应说明（仅供理解，脚本已自动处理）

办公解释器返回的 SSE 数据 stage 类型：
- `generate` — 文本回复
- `code` — 生成的代码
- `execute`/`execution` — 代码执行结果
- `image` — 图片
- `ocr` — OCR 识别

数据分析接口的 finish_reason：
- `stop` — 正常结束
- `text`/`code` — 需要继续请求
- `length`/`sensitive`/`context` — 异常结束

## 关键注意事项

- **不要本地分析数据，所有分析交给小浣熊远程 API**
- 所有接口需 `Authorization: Bearer $RACCOON_API_TOKEN`
- 对话接口只支持 SSE 流式返回，脚本已处理
- 临时文件上传后 7 天过期
- `s3_url` 预签名 URL 约 30 分钟过期

## 参考文档

- `references/API_REFERENCE.md` — 完整 API 参考
- `references/CHEATSHEET.md` — 速查表

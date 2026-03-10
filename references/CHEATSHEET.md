# 小浣熊数据分析 API 速查表

## 认证

```
Authorization: Bearer $RACCOON_API_TOKEN
```

## 数据分析接口

| 操作 | 方法 | 路径 | 关键参数 |
|------|------|------|---------|
| 数据分析对话 | POST | `/api/open/llm/v1/data-analysis/chat-completions` | model, messages[], stream=true |

### messages 结构

| role | 可用 type | 说明 |
|------|-----------|------|
| system | text | 系统提示 |
| user | text, file, description | 用户输入/文件/文件摘要 |
| assistant | text, code, execution, summary | 模型回复/代码/执行结果/总结 |

### finish_reason 快查

| 值 | 动作 |
|----|------|
| text | 继续请求 |
| code | 执行代码后拼接结果继续 |
| stop | 结束 |
| length / sensitive / context | 异常结束 |

---

## 办公解释器接口

### 会话管理

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建会话 | POST | `/api/open/office/v2/sessions` |
| 获取会话 | GET | `/api/open/office/v2/sessions/{session_id}` |
| 会话列表 | GET | `/api/open/office/v2/sessions` |
| 删除会话 | DELETE | `/api/open/office/v2/sessions/{session_id}` |

### 对话交互

| 操作 | 方法 | 路径 |
|------|------|------|
| 发起对话 | POST | `/api/open/office/v2/sessions/{session_id}/chat/conversations` |
| 追问建议 | GET | `/api/open/office/v2/sessions/{session_id}/chat/suggestions` |
| 消息列表 | GET | `/api/open/office/v2/sessions/{session_id}/messages` |

### 文件管理

| 操作 | 方法 | 路径 | Content-Type |
|------|------|------|-------------|
| 上传临时文件(推荐) | POST | `/api/open/office/v2/sessions/default_session/{batch_id}/files` | multipart/form-data |
| 上传到会话(废弃中) | POST | `/api/open/office/v2/sessions/{session_id}/files` | multipart/form-data |
| 文件列表 | GET | `/api/open/office/v2/sessions/files` | - |
| 文件信息 | GET | `/api/open/office/v2/sessions/{session_id}/file_info?file_path=` | - |
| 下载文件 | GET | `/api/open/office/v2/sessions/{session_id}/files?file_path=` | - |
| 删除文件 | DELETE | `/api/open/office/v2/sessions/default_session/{file_id}` | - |

### 生成物

| 操作 | 方法 | 路径 |
|------|------|------|
| 生成物列表 | GET | `/api/open/office/v2/sessions/{session_id}/artifacts` |

---

## 对话请求关键参数

```json
{
  "content": "分析这份数据",
  "verbose": true,
  "enable_web_search": false,
  "deep_think": false,
  "temperature": 1,
  "files": ["file_id_from_session_upload"],
  "upload_file_id": [123],
  "user_at_commands": {
    "asset_filters": [
      {"asset_code": "xxx", "file_uuid": "yyy"}
    ]
  }
}
```

## 文件传递方式对照

| 上传方式 | 对话时使用的参数 |
|---------|--------------|
| 临时文件上传 (default_session) | `upload_file_id: [文件ID]` |
| 会话文件上传 (session_id) | `files: ["文件ID"]` |
| 知识库文件 | `user_at_commands.asset_filters` |

## 常用错误码

| 码 | 含义 | 建议 |
|----|------|------|
| 100012 | 会话不存在 | 检查 session_id |
| 100015 | 沙盒资源不足 | 删除旧会话 |
| 100023 | 文件不存在 | 检查文件路径/ID |
| 200103 | 速率超限 | 等待后重试 |
| 200506 | 当日问题超限 | 次日再试 |
| 300001 | 模型不存在 | 检查 model 值 |

## SSE 流式响应解析

```
data:{"stage":"generate","data":{"delta":"文本内容","session_id":"..."},"status":{"code":0,"message":"success"}}
data:{"stage":"code","data":{"delta":"print('hello')","session_id":"..."},"status":{"code":0,"message":"success"}}
data:{"stage":"execute","data":{"delta":"hello","session_id":"..."},"status":{"code":0,"message":"success"}}
data:{"stage":"image","data":{"delta":"...","session_id":"..."},"status":{"code":0,"message":"success"}}
data:[DONE]
```

stage 枚举: `ocr` | `generate` | `code` | `execute` | `execution` | `image`

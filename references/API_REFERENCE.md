# 小浣熊数据分析 API 参考文档

## 认证方式

所有接口均使用 Bearer Token 认证：

```
Authorization: Bearer $RACCOON_API_TOKEN
```

## 通用响应格式

### 成功响应（非流式）

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 流式响应（SSE）

每行格式：`data:{JSON}`，以 `data:[DONE]` 结束。

### 错误响应

网关层：
```json
{"code": 100001, "message": "empty_params_error", "details": "..."}
```

业务层：
```json
{"error": {"code": 3, "message": "string", "details": []}}
```

---

## 一、数据分析接口

**重要约束：** 对话分析接口生成的所有文件统一保存到 `raccoon/dataanalysis/` 目录下，不得修改此路径。

### 数据分析对话

创建数据分析模型响应，支持流式输出。

- **路径**: `POST /api/open/llm/v1/data-analysis/chat-completions`
- **Content-Type**: `application/json`

#### 请求参数

| 参数 | 类型 | 必须 | 默认值 | 说明 |
|------|------|------|--------|------|
| model | string | 是 | - | 模型ID，如 `SenseChat-Code-DataAnalysis-Excel` |
| messages | object[] | 是 | - | 对话上下文数组 |
| stream | boolean | 否 | true | 只支持 true |
| n | int | 否 | 1 | 生成回复数量 [1,4] |
| max_new_tokens | int | 否 | 自适应 | 最大生成token数 |
| temperature | float | 否 | 0.5 | 温度 [0.1,2] |
| top_p | float | 否 | 0.9 | 核采样 (0,1) |
| repetition_penalty | float | 否 | 1 | 重复惩罚 [1,2]，推荐 [1,1.2] |
| stop | string[] | 否 | `["<\|endofblock\|>","<\|endofmessage\|>"]` | 停止符 |

#### messages 对象

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| role | string | 是 | `system` / `user` / `assistant` |
| type | string | 是 | 取决于 role：`system` → `text`；`user` → `text`/`file`/`description`；`assistant` → `text`/`code`/`execution`/`summary` |
| content | string | 是 | 消息内容 |

#### 响应参数（流式）

| 参数 | 类型 | 说明 |
|------|------|------|
| data.id | string | 消息ID |
| data.choices[].index | int | 回复序号 |
| data.choices[].role | string | 角色 |
| data.choices[].delta | string | 增量内容 |
| data.choices[].type | string | 内容类型：`text` / `code` |
| data.choices[].finish_reason | string | 结束原因（见下） |
| data.usage | object | token用量 |

#### finish_reason 说明

| 值 | 含义 | 处理方式 |
|----|------|---------|
| `text` | 触发会话停止符 | 需要继续请求 |
| `code` | 触发代码停止符 | 需要执行代码后将结果拼接回 messages 继续请求 |
| `stop` | 正常结束 | 对话结束 |
| `length` | 达到最大生成长度 | 对话结束 |
| `sensitive` | 触发敏感词 | 对话结束 |
| `context` | 触发上下文长度限制 | 对话结束 |

---

## 二、办公解释器接口

### 2.1 会话管理

#### 创建会话

- **路径**: `POST /api/open/office/v2/sessions`
- **Content-Type**: `application/json`

| 请求参数 | 类型 | 说明 |
|----------|------|------|
| name | string | 可选，会话名称，不超过70字符 |
| description | string | 可选，会话描述，不超过70字符 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| id | string | 会话ID |
| title | string | 会话标题 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| last_chatted_at | string | 最后聊天时间 |
| language | string | 会话语种 |

#### 获取会话信息

- **路径**: `GET /api/open/office/v2/sessions/{session_id}`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| org_user_id | string | 可选，查询其他用户的会话 |

响应同创建会话。

#### 获取会话列表

- **路径**: `GET /api/open/office/v2/sessions`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| omit_empty_title | boolean | 是否忽略空标题会话 |
| query_title | string | 按标题搜索 |
| org_user_id | integer | 查询其他用户的会话 |
| sort | string | 排序：`+created_at` / `-created_at` / `+updated_at` / `-updated_at` |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| sessions | array | 会话列表 |
| paging | object | 分页信息（limit/offset/total） |

#### 删除会话

- **路径**: `DELETE /api/open/office/v2/sessions/{session_id}`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| org_user_id | string | 可选 |

响应返回被删除会话的信息。

---

### 2.2 对话交互

#### 新增用户对话

- **路径**: `POST /api/open/office/v2/sessions/{session_id}/chat/conversations`
- **Content-Type**: `application/json`
- **返回方式**: 流式 SSE

| 请求参数 | 类型 | 说明 |
|----------|------|------|
| content | string | 必选，对话内容 |
| verbose | boolean | 可选，是否返回代码执行中间信息 |
| deep_think | boolean | 可选，是否开启深度思考 |
| enable_web_search | boolean | 可选，是否开启联网搜索（默认 false） |
| temperature | number | 可选，温度 [0.1,2]，默认 1 |
| edit | integer | 可选，编辑标识（0=普通，其他=编辑消息） |
| message_uuid | string | 可选，用户消息UUID |
| files | string[] | 可选，会话内文件ID列表 |
| upload_file_id | integer[] | 可选，临时上传文件ID列表 |
| user_at_commands | object | 可选，@知识库操作 |
| user_at_commands.asset_filters[].asset_code | string | 知识库代码 |
| user_at_commands.asset_filters[].file_uuid | string | 文件UUID |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| stage | string | 阶段：`ocr`/`generate`/`code`/`execute`/`execution`/`image` |
| data.delta | string | 增量文本 |
| data.finish_reason | string | 结束原因 |
| data.session_id | string | 会话ID |
| data.turn_id | string | 对话轮次ID |
| status.code | integer | 状态码 |
| status.message | string | 状态消息 |

#### 获取追问建议

- **路径**: `GET /api/open/office/v2/sessions/{session_id}/chat/suggestions`

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| suggestions | string[] | 建议列表 |

#### 获取消息列表

- **路径**: `GET /api/open/office/v2/sessions/{session_id}/messages`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| paging.limit | integer | 每页条数 [1,100]，默认 20 |
| paging.offset | integer | 偏移量，默认 0 |
| org_user_id | integer | 可选 |
| verbose | boolean | 是否返回详细信息 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| messages[].role | string | `user`/`assistant`/`system`/`tool` |
| messages[].turn_id | string | 轮次ID |
| messages[].contents[].type | string | `text`/`execution`/`code`/`image` |
| messages[].contents[].content | string | 内容 |
| messages[].contents[].timestamp | integer | 时间戳 |
| paging | object | 分页信息 |

---

### 2.3 文件管理

#### 上传临时文件（推荐）

- **路径**: `POST /api/open/office/v2/sessions/default_session/{batch_id}/files`
- **Content-Type**: `multipart/form-data`
- **说明**: 文件7天过期自动清理

| 路径参数 | 类型 | 说明 |
|----------|------|------|
| batch_id | string | 批次ID（建议用 UUID） |

| 请求参数 | 类型 | 说明 |
|----------|------|------|
| file | file | 上传文件 |
| file_url | string | 可选，文件URL（file 为空时有效） |
| file_name | string | 可选，覆盖文件名 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| file_list[].id | integer | 文件ID（用于 upload_file_id） |
| file_list[].file_name | string | 文件名 |
| file_list[].file_size | integer | 文件大小 |
| file_list[].batch_id | string | 批次ID |
| file_list[].preview_url | string | 预览URL |
| file_list[].preview_data | object | 结构化预览数据 |

#### 上传文件到会话（即将废弃）

- **路径**: `POST /api/open/office/v2/sessions/{session_id}/files`
- **Content-Type**: `multipart/form-data`

| 请求参数 | 类型 | 说明 |
|----------|------|------|
| file | file | 上传文件 |
| file_url | string | 可选，文件URL |
| file_name | string | 可选，覆盖文件名 |
| description | string | 可选，文件描述 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| id | string | 文件ID（用于 files 参数） |
| file_name | string | 文件名 |
| status | string | 文件状态 |

#### 获取文件列表

- **路径**: `GET /api/open/office/v2/sessions/files`

返回用户最后一次上传的临时文件列表。

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| file_list[].id | integer | 文件ID |
| file_list[].file_name | string | 文件名 |
| file_list[].file_size | integer | 大小 |
| file_list[].batch_id | string | 批次ID |
| file_list[].preview_url | string | 预览URL |
| file_list[].preview_data | object | 结构化预览 |

#### 获取文件信息

- **路径**: `GET /api/open/office/v2/sessions/{session_id}/file_info`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| file_path | string | 文件路径 |
| org_user_id | string | 可选 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| file_name | string | 文件名 |
| preview_url | string | 预签名URL（约30分钟过期） |

#### 下载文件

- **路径**: `GET /api/open/office/v2/sessions/{session_id}/files`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| file_path | string | 文件路径 |
| org_user_id | string | 可选 |

返回 `application/octet-stream` 字节流。

#### 删除临时文件

- **路径**: `DELETE /api/open/office/v2/sessions/default_session/{file_id}`

---

### 2.4 生成物管理

#### 获取生成物列表

- **路径**: `GET /api/open/office/v2/sessions/{session_id}/artifacts`

| 查询参数 | 类型 | 说明 |
|----------|------|------|
| org_user_id | string | 可选 |

| 响应参数 | 类型 | 说明 |
|----------|------|------|
| artifacts[].filename | string | 文件名 |
| artifacts[].s3_url | string | S3 预签名下载链接 |
| artifacts[].timestamp | integer | 时间戳 |
| artifacts[].type | string | `image` / `file` |

---

## 三、错误码参考

### 模块特定错误码

| HTTP | 错误码 | 含义 |
|------|--------|------|
| 400 | 100012 | 会话ID不存在 |
| 400 | 100013 | 会话标题太长 |
| 400 | 100015 | 会话沙盒资源不足 |
| 400 | 100016 | 上传总文件数量超限 |
| 400 | 100017 | 上传总文件数据量超限 |
| 400 | 100023 | 文件不存在 |
| 400 | 100030 | 文件类型不允许 |
| 400 | 200404 | 平台沙盒数量超限 |
| 400 | 200506 | 当日问题数量超限 |
| 400 | 300001 | 模型不存在 |
| 429 | 200103 | 请求速率超限 |
| 429 | 200107 | 系统繁忙 |
| 504 | 300004 | 推理代理超时 |
| 500 | 300005 | 推理服务错误 |

### 通用错误码

| HTTP | 错误码 | 含义 |
|------|--------|------|
| 400 | 100001 | 必须参数缺失 |
| 400 | 100002 | 参数格式错误 |
| 400 | 100099 | 其他参数错误 |
| 401 | 200001 | 认证信息缺失 |
| 401 | 200002 | 认证信息格式错误 |
| 401 | 200003 | 认证失败 |
| 400 | 200005 | 用户不存在 |
| 499 | 999990 | 客户端终止请求 |
| 504 | 999991 | 请求超时 |
| 500 | 999999 | 系统内部错误 |

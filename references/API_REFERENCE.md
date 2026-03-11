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

### 1.1 会话管理

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

---

### 1.2 对话交互

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

---

### 1.3 文件管理

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

---

### 1.4 生成物管理

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

## 二、错误码参考

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

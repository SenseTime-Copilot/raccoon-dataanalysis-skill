#!/usr/bin/env python3
"""
小浣熊数据分析 - 统一命令行工具

统一使用数据分析 API 进行数据分析和计算处理

用法:
    python3 main.py analyze --file data.xlsx --prompt "分析数据"
    python3 main.py analyze --prompt "计算斐波那契数列"
    python3 main.py auth-check
    python3 main.py example [1|2]
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import uuid
import warnings

warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

import requests


# ================================================================
# 核心客户端类
# ================================================================

class RaccoonClient:
    """小浣熊 OpenAPI 客户端，内置 SSE 流式解析、重试和生成物下载"""

    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 10, 20]
    STREAM_TIMEOUT = 300
    REQUEST_TIMEOUT = 30

    def __init__(self, host=None, token=None):
        self.host = host or os.environ.get("RACCOON_API_HOST", "")
        self.token = token or os.environ.get("RACCOON_API_TOKEN", "")
        if not self.host:
            print("错误: 未设置 RACCOON_API_HOST 环境变量")
            print("请运行: export RACCOON_API_HOST='https://xiaohuanxiong.com'")
            sys.exit(1)
        if not self.token:
            print("错误: 未设置 RACCOON_API_TOKEN 环境变量")
            print("请运行: export RACCOON_API_TOKEN='your-api-token'")
            sys.exit(1)

    @property
    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    @property
    def _upload_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method, path, json_data=None, params=None, timeout=None):
        url = f"{self.host}{path}"
        timeout = timeout or self.REQUEST_TIMEOUT
        resp = requests.request(
            method, url, headers=self._headers,
            json=json_data, params=params, timeout=timeout,
        )
        if resp.status_code != 200:
            raise APIError(resp.status_code, resp.text)
        body = resp.json()
        if body.get("code") != 0:
            raise APIError(body.get("code"), body.get("message", "unknown error"))
        return body.get("data", {})

    def create_session(self, name="数据分析会话"):
        return self._request("POST", "/api/open/office/v2/sessions", {"name": name})




    def upload_temp_file(self, file_path):
        """上传临时文件，返回 file_id (int)"""
        batch_id = str(uuid.uuid4())
        url = f"{self.host}/api/open/office/v2/sessions/default_session/{batch_id}/files"
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            resp = requests.post(
                url, headers=self._upload_headers,
                files={"file": (filename, f)}, timeout=60,
            )
        if resp.status_code != 200:
            raise APIError(resp.status_code, resp.text)
        body = resp.json()
        file_list = body.get("data", {}).get("file_list", [])
        if not file_list:
            raise APIError(0, "上传文件失败: 返回空 file_list")
        return file_list[0]["id"]

    def list_files(self):
        return self._request("GET", "/api/open/office/v2/sessions/files").get("file_list", [])

    def get_file_info(self, session_id, file_path):
        return self._request("GET", f"/api/open/office/v2/sessions/{session_id}/file_info",
                             params={"file_path": file_path})


    def chat(self, session_id, content, upload_file_ids=None, files=None,
             verbose=True, deep_think=False, temperature=1, retries=None):
        """发起对话并完整解析 SSE 响应，返回结构化结果"""
        retries = retries if retries is not None else self.MAX_RETRIES
        data = {
            "content": content,
            "verbose": verbose,
            "enable_web_search": False,
            "deep_think": deep_think,
            "temperature": temperature,
            "message_uuid": str(uuid.uuid4()),
            "edit": 0,
        }
        if upload_file_ids:
            data["upload_file_id"] = upload_file_ids
        if files:
            data["files"] = files

        last_error = None
        for attempt in range(retries + 1):
            try:
                return self._stream_chat(session_id, data)
            except (RetryableError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_error = e
                if attempt < retries:
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    print(f"[重试 {attempt+1}/{retries}] {e} - 等待 {delay}s...", file=sys.stderr)
                    time.sleep(delay)
        raise last_error

    def _stream_chat(self, session_id, data):
        url = f"{self.host}/api/open/office/v2/sessions/{session_id}/chat/conversations"
        resp = requests.post(
            url, headers=self._headers, json=data,
            stream=True, timeout=self.STREAM_TIMEOUT,
        )
        if resp.status_code == 429:
            raise RetryableError(f"HTTP 429: 请求速率超限")
        if resp.status_code == 504:
            raise RetryableError(f"HTTP 504: 推理代理超时")
        if resp.status_code != 200:
            raise APIError(resp.status_code, resp.text[:300])

        result = ChatResult()
        current_stage = ""

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if not line_str.startswith("data:"):
                continue
            json_str = line_str[5:].strip()
            if json_str == "[DONE]":
                result.done = True
                break
            try:
                obj = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            status_code = obj.get("status", {}).get("code", 0)
            if status_code != 0:
                msg = obj.get("status", {}).get("message", "")
                raise APIError(status_code, msg)

            stage = obj.get("stage", "")
            delta = obj.get("data", {}).get("delta", "")
            finish_reason = obj.get("data", {}).get("finish_reason", "")
            session_id_resp = obj.get("data", {}).get("session_id", "")
            turn_id = obj.get("data", {}).get("turn_id", "")

            if session_id_resp:
                result.session_id = session_id_resp
            if turn_id:
                result.turn_id = turn_id
            if finish_reason:
                result.finish_reason = finish_reason

            if not delta:
                continue

            current_stage = stage or current_stage

            if current_stage == "generate":
                result.text += delta
                print(delta, end="", flush=True)
            elif current_stage == "code":
                result.code_buffer += delta
            elif current_stage in ("execute", "execution"):
                if "context canceled" in delta:
                    raise RetryableError(f"沙盒执行错误: context canceled")
                result.execution_buffer += delta
            elif current_stage == "image":
                result.image_buffer += delta
            elif current_stage == "ocr":
                result.ocr_buffer += delta

            if stage and stage != current_stage:
                result.flush_buffer(current_stage)
                current_stage = stage

        result.flush_buffer(current_stage)
        if result.text:
            print()

        if not result.done:
            raise RetryableError("SSE 流中途断开（未收到 [DONE]）")

        return result

    def get_artifacts(self, session_id):
        data = self._request("GET", f"/api/open/office/v2/sessions/{session_id}/artifacts")
        return data.get("artifacts", [])

    def download_artifacts(self, session_id, output_dir="./raccoon/dataanalysis"):
        """下载所有生成物到本地，返回文件路径列表"""
        artifacts = self.get_artifacts(session_id)
        if not artifacts:
            print("无生成物")
            return []

        os.makedirs(output_dir, exist_ok=True)
        downloaded = []
        for art in artifacts:
            s3_url = art.get("s3_url", "")
            filename = art.get("filename", f"artifact_{art.get('timestamp', 'unknown')}")
            if not s3_url:
                continue
            local_path = os.path.join(output_dir, filename)
            try:
                resp = requests.get(s3_url, timeout=60)
                if resp.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                    downloaded.append(local_path)
                    print(f"  已下载: {local_path} ({art.get('type', 'unknown')})")
                else:
                    print(f"  下载失败 [{resp.status_code}]: {filename}", file=sys.stderr)
            except Exception as e:
                print(f"  下载异常: {filename} - {e}", file=sys.stderr)
        return downloaded


class ChatResult:
    """对话结果容器，按 stage 分类存储"""

    def __init__(self):
        self.text = ""
        self.code = []
        self.execution = []
        self.images = []
        self.ocr = []
        self.finish_reason = ""
        self.session_id = ""
        self.turn_id = ""
        self.usage = {}
        self.done = False
        self.code_buffer = ""
        self.execution_buffer = ""
        self.image_buffer = ""
        self.ocr_buffer = ""

    def flush_buffer(self, stage):
        if stage == "code" and self.code_buffer:
            self.code.append(self.code_buffer)
            self.code_buffer = ""
        elif stage in ("execute", "execution") and self.execution_buffer:
            self.execution.append(self.execution_buffer)
            self.execution_buffer = ""
        elif stage == "image" and self.image_buffer:
            self.images.append(self.image_buffer)
            self.image_buffer = ""
        elif stage == "ocr" and self.ocr_buffer:
            self.ocr.append(self.ocr_buffer)
            self.ocr_buffer = ""

    def summary(self):
        parts = []
        if self.text:
            parts.append(f"文本回复: {len(self.text)} 字符")
        if self.code:
            parts.append(f"代码段: {len(self.code)} 个")
        if self.execution:
            parts.append(f"执行结果: {len(self.execution)} 个")
        if self.images:
            parts.append(f"图片: {len(self.images)} 个")
        if self.finish_reason:
            parts.append(f"结束原因: {self.finish_reason}")
        return " | ".join(parts) if parts else "无内容"

    def __repr__(self):
        return f"<ChatResult {self.summary()}>"


class APIError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"API错误 [{code}]: {message}")


class RetryableError(Exception):
    pass


# ================================================================
# 工具函数
# ================================================================

def check_environment():
    """检查环境变量配置"""
    host = os.environ.get("RACCOON_API_HOST", "")
    token = os.environ.get("RACCOON_API_TOKEN", "")

    if not host:
        print("错误: 未设置 RACCOON_API_HOST 环境变量", file=sys.stderr)
        print("请运行: export RACCOON_API_HOST='https://xiaohuanxiong.com'", file=sys.stderr)
        return False
    if not token:
        print("错误: 未设置 RACCOON_API_TOKEN 环境变量", file=sys.stderr)
        print("请运行: export RACCOON_API_TOKEN='your-api-token'", file=sys.stderr)
        return False

    print(f"✓ RACCOON_API_HOST: {host}")
    print(f"✓ RACCOON_API_TOKEN: 已设置({len(token)}字符)")
    return True


def open_file(path):
    """跨平台打开文件"""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", path], check=False)
        elif system == "Linux":
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


# ================================================================
# 子命令：分析文件/对话
# ================================================================

def cmd_analyze(args):
    """文件分析或纯对话功能"""
    if not check_environment():
        sys.exit(1)

    if args.file and not os.path.isfile(args.file):
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        client = RaccoonClient()

        # 统一使用数据分析接口（无论是否有文件）
        session_name = args.session_name or f"分析: {os.path.basename(args.file) if args.file else args.prompt[:20]}"
        print(f"[1/4] 创建会话: {session_name}")
        session = client.create_session(session_name)
        session_id = session["id"]
        print(f"      会话ID: {session_id}")

        upload_file_ids = []
        # 如果有文件，先上传
        if args.file:
            print(f"[2/4] 上传文件: {args.file}")
            file_id = client.upload_temp_file(args.file)
            upload_file_ids = [file_id]
            print(f"      文件ID: {file_id}")

        print(f"[{3 if args.file else 2}/4] 发起对话: {args.prompt}")
        print("-" * 60)
        result = client.chat(
            session_id, args.prompt,
            upload_file_ids=upload_file_ids,
        )

        print("-" * 60)
        print(f"[对话完成] {result.summary()}")

        if args.show_code and result.code:
            print("\n--- 执行的代码 ---")
            for i, code in enumerate(result.code, 1):
                print(f"\n# 代码段 {i}:")
                print(code)

        if args.show_execution and result.execution:
            print("\n--- 执行结果 ---")
            for i, exe in enumerate(result.execution, 1):
                print(f"\n# 结果 {i}:")
                print(exe)

        if not args.no_download:
            print(f"\n[{4 if args.file else 3}/4] 获取生成物...")
            # 统一使用 raccoon/dataanalysis 目录
            output_dir = "./raccoon/dataanalysis"
            downloaded = client.download_artifacts(session_id, output_dir=output_dir)
            if downloaded:
                print(f"      共下载 {len(downloaded)} 个文件到 {output_dir}/")
                if not args.no_open:
                    images = [p for p in downloaded if p.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))]
                    if images:
                        open_file(images[0])
            else:
                print("      无生成物")
        else:
            print(f"\n[{4 if args.file else 3}/4] 跳过生成物下载")

        print(f"\n完成! 会话ID: {session_id}")

    except RetryableError as e:
        print(f"\n对话失败（已重试）: {e}", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"\nAPI 错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n未预期错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ================================================================
# 子命令：认证检查
# ================================================================

def cmd_auth_check(args):
    """验证认证配置"""
    host = os.environ.get("RACCOON_API_HOST", "")
    token = os.environ.get("RACCOON_API_TOKEN", "")

    if not host:
        print("错误: 未设置 RACCOON_API_HOST 环境变量")
        print("请运行: export RACCOON_API_HOST='https://xiaohuanxiong.com'")
        sys.exit(1)
    if not token:
        print("错误: 未设置 RACCOON_API_TOKEN 环境变量")
        print("请运行: export RACCOON_API_TOKEN='your-api-token'")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    url = f"{host}/api/open/office/v2/sessions"
    try:
        resp = requests.get(url, headers=headers, params={"paging.limit": 1}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                print("认证验证成功!")
                print(f"  API Host: {host}")
                print(f"  Token: {token[:20]}...{token[-10:]}")
                sessions = data.get("data", {}).get("sessions", [])
                print(f"  现有会话数: {data.get('data', {}).get('paging', {}).get('total', len(sessions))}")
                return True
        if resp.status_code == 401:
            print("认证失败: Token 无效或已过期")
        else:
            print(f"请求失败: HTTP {resp.status_code}")
            print(f"响应: {resp.text[:200]}")
    except requests.exceptions.ConnectionError:
        print(f"连接失败: 无法连接到 {host}")
    except Exception as e:
        print(f"验证异常: {e}")

    return False


# ================================================================
# 子命令：使用示例
# ================================================================

def stream_request_example(host, headers, method, path, data=None, files=None):
    """发送流式请求并打印增量输出（示例用）"""
    url = f"{host}{path}"
    if method == "POST" and files:
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        resp = requests.post(url, headers=h, files=files, stream=True, timeout=120)
    elif method == "POST":
        resp = requests.post(url, headers=headers, json=data, stream=True, timeout=120)
    else:
        resp = requests.get(url, headers=headers, params=data, timeout=30)
        return resp.json().get("data") if resp.status_code == 200 else None

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    result_text = ""
    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8") if isinstance(line, bytes) else line
        if not line_str.startswith("data:"):
            continue
        json_str = line_str[5:].strip()
        if json_str == "[DONE]":
            break
        try:
            obj = json.loads(json_str)
            stage = obj.get("stage", "")
            delta = obj.get("data", {}).get("delta", "")
            if delta and stage in ("generate", "image"):
                print(delta, end="", flush=True)
                result_text += delta
        except json.JSONDecodeError:
            pass
    print()
    return result_text


def example_data_analysis_flow():
    """数据分析完整流程示例"""
    print("=" * 60)
    print("示例2: 数据分析完整流程")
    print("=" * 60)

    host = os.environ.get("RACCOON_API_HOST", "")
    token = os.environ.get("RACCOON_API_TOKEN", "")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    print("\n[步骤1] 创建会话...")
    resp = requests.post(
        f"{host}/api/open/office/v2/sessions",
        headers=headers,
        json={"name": "Python示例会话"},
        timeout=10,
    )
    session_data = resp.json().get("data", {})
    session_id = session_data.get("id")
    if not session_id:
        print("创建会话失败")
        return
    print(f"  会话ID: {session_id}")

    print("\n[步骤2] 上传临时文件...")
    batch_id = str(uuid.uuid4())
    csv_content = "name,age,score\nAlice,25,88\nBob,30,92\nCarol,28,85\nDave,35,95\nEve,22,78"
    upload_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
    resp = requests.post(
        f"{host}/api/open/office/v2/sessions/default_session/{batch_id}/files",
        headers=upload_headers,
        files={"file": ("sample_data.csv", csv_content.encode(), "text/csv")},
        timeout=30,
    )
    upload_result = resp.json().get("data", {})
    file_list = upload_result.get("file_list", [])
    if not file_list:
        print("上传文件失败")
        return
    file_id = file_list[0]["id"]
    print(f"  文件ID: {file_id}, 文件名: {file_list[0]['file_name']}")

    print("\n[步骤3] 发起对话分析...")
    chat_data = {
        "content": "帮我分析这份数据，画一个成绩分布柱状图",
        "verbose": True,
        "enable_web_search": False,
        "deep_think": False,
        "message_uuid": str(uuid.uuid4()),
        "upload_file_id": [file_id],
    }
    stream_request_example(
        host, headers, "POST",
        f"/api/open/office/v2/sessions/{session_id}/chat/conversations",
        chat_data,
    )

    print(f"\n会话ID: {session_id}")



def cmd_example(args):
    """运行使用示例"""
    if not check_environment():
        sys.exit(1)

    examples = {
        "1": ("数据分析完整流程", example_data_analysis_flow),
    }

    if args.example_id and args.example_id in examples:
        examples[args.example_id][1]()
    else:
        print("小浣熊数据分析 API 示例")
        for k, (desc, _) in examples.items():
            print(f"  {k} - {desc}")
        print("\n运行全部示例...")
        for _, fn in examples.values():
            fn()
            print()


# ================================================================
# 主程序
# ================================================================

def main():
    parser = argparse.ArgumentParser(description="小浣熊数据分析 - 统一命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    analyze_parser = subparsers.add_parser("analyze", help="分析文件或进行对话")
    analyze_parser.add_argument("--file", "-f", help="待分析的文件路径")
    analyze_parser.add_argument("--prompt", "-p", required=True, help="分析需求描述")
    analyze_parser.add_argument("--output", "-o", default="./raccoon/dataanalysis", help="生成物输出目录（已固定为 ./raccoon/dataanalysis）")
    analyze_parser.add_argument("--session-name", help="会话名称")
    analyze_parser.add_argument("--no-download", action="store_true", help="不下载生成物")
    analyze_parser.add_argument("--no-open", action="store_true", help="不自动打开生成的图片")
    analyze_parser.add_argument("--show-code", action="store_true", help="显示执行的代码")
    analyze_parser.add_argument("--show-execution", action="store_true", help="显示代码执行结果")

    subparsers.add_parser("auth-check", help="检查认证配置")

    example_parser = subparsers.add_parser("example", help="运行使用示例")
    example_parser.add_argument("example_id", nargs="?", choices=["1"], help="示例编号")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "auth-check":
        cmd_auth_check(args)
    elif args.command == "example":
        cmd_example(args)


if __name__ == "__main__":
    main()

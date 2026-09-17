# ===== 飞书文档/表格写入 MCP 服务 =====

import os

import time

import requests

from mcp.server.fastmcp import FastMCP

# 飞书应用凭证（从环境变量读取，部署时在Render里配置）

APP\_ID = os.environ.get("FEISHU\_APP\_ID", "")

APP\_SECRET = os.environ.get("FEISHU\_APP\_SECRET", "")

BASE = "https://open.feishu.cn/open-apis"

# token 缓存（自动刷新，不用管）

\_token = {"value": None, "expire": 0}

def get\_token():

&#x20;   now = time.time()

&#x20;   if \_token\["value"] and now < \_token\["expire"] - 120:

&#x20;       return \_token\["value"]

&#x20;   r = requests.post(

&#x20;       f"{BASE}/auth/v3/tenant\_access\_token/internal",

&#x20;       json={"app\_id": APP\_ID, "app\_secret": APP\_SECRET}

&#x20;   ).json()

&#x20;   if r.get("code") != 0:

&#x20;       raise Exception(f"获取飞书token失败: {r}")

&#x20;   \_token\["value"] = r\["tenant\_access\_token"]

&#x20;   \_token\["expire"] = now + r.get("expire", 7200)

&#x20;   return \_token\["value"]

def hd():

&#x20;   return {"Authorization": f"Bearer {get\_token()}", "Content-Type": "application/json"}

# 创建 MCP 服务

mcp = FastMCP("feishu-doc-writer")

@mcp.tool()

def create\_doc(title: str, content: str) -> str:

&#x20;   """创建飞书文档并写入正文内容，返回文档链接。

&#x20;   正文支持标题标记：# 一级标题、## 二级标题、### 三级标题，其他行按普通段落处理。

&#x20;   Args:

&#x20;       title: 文档标题，例如：XX产品适配评估报告

&#x20;       content: 文档正文，多行内容用换行分隔

&#x20;   Returns:

&#x20;       飞书文档的访问链接

&#x20;   """

&#x20;   r = requests.post(f"{BASE}/docx/v1/documents", headers=hd(),

&#x20;                     json={"title": title}).json()

&#x20;   if r.get("code") != 0:

&#x20;       return f"创建文档失败: {r.get('msg', str(r))}"

&#x20;   doc\_id = r\["data"]\["document"]\["document\_id"]

&#x20;   if content and content.strip():

&#x20;       blocks = \[]

&#x20;       for line in content.strip().split("\n"):

&#x20;           line = line.strip()

&#x20;           if not line:

&#x20;               continue

&#x20;           if line.startswith("### "):

&#x20;               blocks.append({"block\_type": 5, "heading3": {

&#x20;                   "elements": \[{"text\_run": {"content": line\[4:]}}]}})

&#x20;           elif line.startswith("## "):

&#x20;               blocks.append({"block\_type": 4, "heading2": {

&#x20;                   "elements": \[{"text\_run": {"content": line\[3:]}}]}})

&#x20;           elif line.startswith("# "):

&#x20;               blocks.append({"block\_type": 3, "heading1": {

&#x20;                   "elements": \[{"text\_run": {"content": line\[2:]}}]}})

&#x20;           else:

&#x20;               blocks.append({"block\_type": 2, "text": {

&#x20;                   "elements": \[{"text\_run": {"content": line}}]}})

&#x20;       # 分批插入，每批最多50个段落

&#x20;       for i in range(0, len(blocks), 50):

&#x20;           requests.post(

&#x20;               f"{BASE}/docx/v1/documents/{doc\_id}/blocks/{doc\_id}/children",

&#x20;               headers=hd(), json={"children": blocks\[i:i+50], "index": -1})

&#x20;   # 设置为「组织内获得链接的人可阅读」

&#x20;   requests.patch(

&#x20;       f"{BASE}/drive/v1/permissions/{doc\_id}/public?type=docx",

&#x20;       headers=hd(), json={"link\_share\_entity": "tenant\_readable"})

&#x20;   return f"文档创建成功，链接：https://feishu.cn/docx/{doc\_id}"

@mcp.tool()

def create\_sheet(title: str, headers: str, rows: str) -> str:

&#x20;   """创建飞书电子表格并写入表头和数据，返回表格链接。

&#x20;   Args:

&#x20;       title: 表格标题，例如：六维评分表

&#x20;       headers: 表头文字，多列用英文逗号分隔，例如：维度,得分,匹配状态

&#x20;       rows: 数据行，每行用英文分号分隔，每行内的列用英文逗号分隔，

&#x20;             例如：功能匹配,85,MATCH;价格适配,70,PARTIAL;交付周期,90,MATCH

&#x20;   Returns:

&#x20;       飞书表格的访问链接

&#x20;   """

&#x20;   r = requests.post(f"{BASE}/sheets/v3/spreadsheets", headers=hd(),

&#x20;                     json={"title": title}).json()

&#x20;   if r.get("code") != 0:

&#x20;       return f"创建表格失败: {r.get('msg', str(r))}"

&#x20;   token = r\["data"]\["spreadsheet"]\["spreadsheet\_token"]

&#x20;   q = requests.get(f"{BASE}/sheets/v3/spreadsheets/{token}/sheets/query",

&#x20;                    headers=hd()).json()

&#x20;   sheet\_id = q\["data"]\["sheets"]\[0]\["sheet\_id"]

&#x20;   values = \[]

&#x20;   if headers and headers.strip():

&#x20;       values.append(\[h.strip() for h in headers.split(",")])

&#x20;   if rows and rows.strip():

&#x20;       for row in rows.split(";"):

&#x20;           if row.strip():

&#x20;               values.append(\[c.strip() for c in row.split(",")])

&#x20;   if values:

&#x20;       end\_col = chr(ord('A') + len(values\[0]) - 1)

&#x20;       rng = f"{sheet\_id}!A1:{end\_col}{len(values)}"

&#x20;       requests.put(f"{BASE}/sheets/v2/spreadsheets/{token}/values",

&#x20;                    headers=hd(),

&#x20;                    json={"valueRange": {"range": rng, "values": values}})

&#x20;   # 设置为「组织内获得链接的人可阅读」

&#x20;   requests.patch(

&#x20;       f"{BASE}/drive/v1/permissions/{token}/public?type=sheet",

&#x20;       headers=hd(), json={"link\_share\_entity": "tenant\_readable"})

&#x20;   return f"表格创建成功，链接：https://feishu.cn/sheets/{token}"

@mcp.tool()

def append\_sheet(sheet\_token: str, rows: str) -> str:

&#x20;   """向已有的飞书表格末尾追加数据行。

&#x20;   Args:

&#x20;       sheet\_token: 表格标识，从表格URL中获取（https://feishu.cn/sheets/ 后面那串字符）

&#x20;       rows: 要追加的数据，每行用英文分号分隔，列用英文逗号分隔

&#x20;   Returns:

&#x20;       追加结果说明

&#x20;   """

&#x20;   q = requests.get(f"{BASE}/sheets/v3/spreadsheets/{sheet\_token}/sheets/query",

&#x20;                    headers=hd()).json()

&#x20;   sid = q\["data"]\["sheets"]\[0]\["sheet\_id"]

&#x20;   values = \[]

&#x20;   for row in rows.split(";"):

&#x20;       if row.strip():

&#x20;           values.append(\[c.strip() for c in row.split(",")])

&#x20;   r = requests.post(f"{BASE}/sheets/v2/spreadsheets/{sheet\_token}/values\_append",

&#x20;                     headers=hd(),

&#x20;                     json={"valueRange": {"range": f"{sid}!A1", "values": values}}).json()

&#x20;   if r.get("code") != 0:

&#x20;       return f"追加失败: {r.get('msg', str(r))}"

&#x20;   return "数据追加成功"

# 启动服务（监听平台分配的端口）

if \_\_name\_\_ == "\_\_main\_\_":

&#x20;   port = int(os.environ.get("PORT", 8000))

&#x20;   mcp.run(transport="streamable-http", host="0.0.0.0", port=port)

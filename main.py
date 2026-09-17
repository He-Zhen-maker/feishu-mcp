import os
import time
import requests
from mcp.server.fastmcp import FastMCP

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
BASE = "https://open.feishu.cn/open-apis"

_token = {"value": None, "expire": 0}

def get_token():
    now = time.time()
    if _token["value"] and now < _token["expire"] - 120:
        return _token["value"]
    r = requests.post(
        BASE + "/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    ).json()
    if r.get("code") != 0:
        raise Exception("获取飞书token失败: " + str(r))
    _token["value"] = r["tenant_access_token"]
    _token["expire"] = now + r.get("expire", 7200)
    return _token["value"]

def hd():
    return {"Authorization": "Bearer " + get_token(), "Content-Type": "application/json"}

mcp = FastMCP("feishu-doc-writer")


@mcp.tool()
def create_doc(title: str, content: str) -> str:
    """创建飞书文档并写入正文内容，返回文档链接。正文支持标题标记：# 一级标题、## 二级标题、### 三级标题，其他行按普通段落处理。

    Args:
        title: 文档标题
        content: 文档正文，多行内容用换行分隔
    Returns:
        飞书文档的访问链接
    """
    r = requests.post(BASE + "/docx/v1/documents", headers=hd(),
                      json={"title": title}).json()
    if r.get("code") != 0:
        return "创建文档失败: " + str(r.get("msg", str(r)))
    doc_id = r["data"]["document"]["document_id"]

    if content and content.strip():
        blocks = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("### "):
                blocks.append({"block_type": 5, "heading3": {
                    "elements": [{"text_run": {"content": line[4:]}}]}})
            elif line.startswith("## "):
                blocks.append({"block_type": 4, "heading2": {
                    "elements": [{"text_run": {"content": line[3:]}}]}})
            elif line.startswith("# "):
                blocks.append({"block_type": 3, "heading1": {
                    "elements": [{"text_run": {"content": line[2:]}}]}})
            else:
                blocks.append({"block_type": 2, "text": {
                    "elements": [{"text_run": {"content": line}}]}})
        for i in range(0, len(blocks), 50):
            requests.post(
                BASE + "/docx/v1/documents/" + doc_id + "/blocks/" + doc_id + "/children",
                headers=hd(), json={"children": blocks[i:i+50], "index": -1})

    requests.patch(
        BASE + "/drive/v1/permissions/" + doc_id + "/public?type=docx",
        headers=hd(), json={"link_share_entity": "tenant_readable"})

    return "文档创建成功，链接：https://feishu.cn/docx/" + doc_id


@mcp.tool()
def create_sheet(title: str, headers: str, rows: str) -> str:
    """创建飞书电子表格并写入表头和数据，返回表格链接。

    Args:
        title: 表格标题
        headers: 表头文字，多列用英文逗号分隔，例如：维度,得分,匹配状态
        rows: 数据行，每行用英文分号分隔，每行内的列用英文逗号分隔
    Returns:
        飞书表格的访问链接
    """
    r = requests.post(BASE + "/sheets/v3/spreadsheets", headers=hd(),
                      json={"title": title}).json()
    if r.get("code") != 0:
        return "创建表格失败: " + str(r.get("msg", str(r)))
    token = r["data"]["spreadsheet"]["spreadsheet_token"]

    q = requests.get(BASE + "/sheets/v3/spreadsheets/" + token + "/sheets/query",
                     headers=hd()).json()
    sheet_id = q["data"]["sheets"][0]["sheet_id"]

    values = []
    if headers and headers.strip():
        values.append([h.strip() for h in headers.split(",")])
    if rows and rows.strip():
        for row in rows.split(";"):
            if row.strip():
                values.append([c.strip() for c in row.split(",")])

    if values:
        end_col = chr(ord("A") + len(values[0]) - 1)
        rng = sheet_id + "!A1:" + end_col + str(len(values))
        requests.put(BASE + "/sheets/v2/spreadsheets/" + token + "/values",
                     headers=hd(),
                     json={"valueRange": {"range": rng, "values": values}})

    requests.patch(
        BASE + "/drive/v1/permissions/" + token + "/public?type=sheet",
        headers=hd(), json={"link_share_entity": "tenant_readable"})

    return "表格创建成功，链接：https://feishu.cn/sheets/" + token


@mcp.tool()
def append_sheet(sheet_token: str, rows: str) -> str:
    """向已有的飞书表格末尾追加数据行。

    Args:
        sheet_token: 表格标识，从表格URL中获取（https://feishu.cn/sheets/ 后面那串字符）
        rows: 要追加的数据，每行用英文分号分隔，列用英文逗号分隔
    Returns:
        追加结果说明
    """
    q = requests.get(BASE + "/sheets/v3/spreadsheets/" + sheet_token + "/sheets/query",
                     headers=hd()).json()
    sid = q["data"]["sheets"][0]["sheet_id"]

    values = []
    for row in rows.split(";"):
        if row.strip():
            values.append([c.strip() for c in row.split(",")])

    r = requests.post(BASE + "/sheets/v2/spreadsheets/" + sheet_token + "/values_append",
                      headers=hd(),
                      json={"valueRange": {"range": sid + "!A1", "values": values}}).json()
    if r.get("code") != 0:
        return "追加失败: " + str(r.get("msg", str(r)))
    return "数据追加成功"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)

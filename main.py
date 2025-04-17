# -*- coding: utf-8 -*-
"""
Created on Thu Apr 10 15:57:51 2025

@author: 殇璃
"""

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import requests, json, base64, os
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Image Search & Upload API",
    description="Search image from Bing and upload to imgbb",
    version="1.0",
    openapi_version="3.1.0",
    servers=[
        {"url": "https://image-search-plugin.onrender.com"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源访问（可以改为指定域名）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有请求方法：GET、POST、OPTIONS 等
    allow_headers=["*"],  # 允许所有请求头
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def plugin_manifest():
    return FileResponse("static/ai-plugin.json")

def is_supported_image_format(content_type):
    """判断图片类型是否支持"""
    return any(fmt in content_type for fmt in ["jpeg", "jpg", "png"])

def search_image_url(query):
    """提取 Bing 上第一个符合要求的图片 URL（仅限 jpeg/jpg/png）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
        "Referer": "https://www.bing.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Cookie": (
            "MUID=3F8E0A9495E065001ADE1FD29464649B; "
            "ANON=A=C1466B969998C3B675A54C36FFFFFFFF&E=1e8a&W=1; "
            "SRCHUID=V=2&GUID=B15266CB168A45819FA6ADF106485126&dmnchg=1; "
            "SRCHUSR=DOB=20241129&T=1743509671000&POEX=W&DS=1; "
            "SRCHD=AF=NOFORM; "
            "_EDGE_V=1; "
            "_EDGE_S=SID=256959450C856AD1367F4C940D576B0A&mkt=zh-hk; "
            "_SS=SID=2CF57D8A79E862760AD5684478AB63B9&PC=NMTS&R=398&RB=398&GB=0&RG=0&RP=398; "
            "USRLOC=HS=1&ELOC=LAT=39.10505676269531|LON=117.1767578125|N=%E5%8D%97%E5%BC%80%E5%8C%BA%EF%BC%8C%E5%A4%A9%E6%B4%A5%E5%B8%82|ELT=2|&CLOC=LAT=39.10505549307363|LON=117.17675500064105|A=733.4464586120832|TS=250417063042|SRC=W&BID=MjUwNDE3MTQzMDQxXzEzZTUzMmNjMzhiNDhhMGJkODMzNWE0M2UwMzRhODA1YWE2ZWFhMGMzYTRhMTBlOGNjZWE3MWNiNzEzNjI2MDA="
        )
    }

    res = requests.get(f"https://www.bing.com/images/search?q={query}", headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.find_all("a", class_="iusc")

    for item in items[:5]:
        try:
            metadata = json.loads(item.get("m"))
            image_url = metadata.get("murl")
            if not image_url:
                continue

            # 提前 HEAD 请求检查格式
            head_res = requests.head(image_url, timeout=5)
            content_type = head_res.headers.get("Content-Type", "")

            if head_res.status_code == 200 and is_supported_image_format(content_type):
                return image_url
        except Exception:
            continue

    raise Exception("找不到符合格式的图片 URL（仅支持 jpg/jpeg/png）")

def download_image(image_url):
    """下载图片字节内容"""
    res = requests.get(image_url, stream=True, timeout=10)
    content_type = res.headers.get("Content-Type", "")

    if res.status_code == 200 and content_type.startswith("image"):
        if is_supported_image_format(content_type):
            return res.content
        else:
            raise Exception(f"不支持的图片格式：{content_type}")
    raise Exception("图片下载失败或内容格式不对")


def upload_to_imgbb(image_bytes, imgbb_api_key):
    """将图片上传至 imgbb 并返回图片 URL"""
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "key": imgbb_api_key,
        "image": image_base64
    }
    res = requests.post("https://api.imgbb.com/1/upload", data=payload)
    json_data = res.json()
    if res.status_code == 200 and json_data.get("success") == True:
        return json_data["data"]["url"]
    raise Exception("上传失败，请检查响应内容")

@app.get("/get_image_url")
def get_image_url(product: str = Query(..., description="商品或关键词"), imgbb_key: str = Query(None, description="在 imgbb 获取你的 API key")):
    try:
         # 如果请求参数中没有提供 imgbb_key，则从环境变量中读取
        if not imgbb_key:
            imgbb_key = os.getenv("IMGBB_API_KEY")
            if not imgbb_key:
                raise ValueError("未提供 imgbb API 密钥，且环境变量中未设置 IMGBB_API_KEY")
                
        image_url = search_image_url(product)
        image_bytes = download_image(image_url)
        final_url = upload_to_imgbb(image_bytes, imgbb_key)
        return JSONResponse(content={
            "status": "success",
            "product": product,
            "url": final_url,
            "markdown_embed": f"![{product}]({final_url})"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # 强制设定 OpenAPI 版本 & servers 字段
    openapi_schema["openapi"] = "3.1.0"
    openapi_schema["servers"] = [
        {"url": "https://image-search-plugin.onrender.com"}
    ]
    # ✅ 补全 get_image_url 的响应结构
    if "/get_image_url" in openapi_schema["paths"]:
        get_op = openapi_schema["paths"]["/get_image_url"]["get"]
        if "responses" in get_op and "200" in get_op["responses"]:
            get_op["responses"]["200"]["content"]["application/json"]["schema"] = {
                "type": "object",
                "properties": {
                    "status": { "type": "string" },
                    "product": { "type": "string" },
                    "url": { "type": "string", "format": "uri" },
                    "markdown_embed": { "type": "string" }
                }
            }
            
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# 应用新的 openapi 定义
app.openapi = custom_openapi

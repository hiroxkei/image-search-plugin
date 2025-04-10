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

app = FastAPI(title="Image Search & Upload API", description="Search image from Bing and upload to imgbb")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def plugin_manifest():
    return FileResponse("static/ai-plugin.json")

def search_image_url(query):
    """提取 Bing 第一张高清图 URL（使用 murl 字段）"""
    headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bing.com/"
}
    res = requests.get(f"https://www.bing.com/images/search?q={query}", headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    items = soup.find_all("a", class_="iusc")
    for item in items:
        try:
            metadata = json.loads(item.get("m"))
            image_url = metadata.get("murl")
            if image_url:
                return image_url
        except Exception:
            continue
    raise Exception("找不到有效的图片 URL")

def download_image(image_url):
    """下载图片字节内容"""
    res = requests.get(image_url, stream=True, timeout=10)
    content_type = res.headers.get("Content-Type", "")
    if res.status_code == 200 and res.headers.get("Content-Type", "").startswith("image"):
        if any(fmt in content_type for fmt in ["jpeg", "jpg", "png"]):
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
def get_image_url(product: str = Query(..., description="商品或关键词"), imgbb_key: str = Query(..., description="8159803498668ccc92ad1f2fb694dcc1")):
    try:
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

"""Web 面板（M5 交付，依赖 web extra；fastapi/uvicorn 惰性导入）。

免构建：FastAPI + 零依赖内联单页（vanilla JS + inline CSS），页面 0 外链、
断网可演示；/docs 与 /redoc 显式关闭（Swagger UI 引 CDN）。
"""

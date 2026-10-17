# 氟化工生产技术知识库

把《氟化工生产技术》（胡伟主编，科学出版社，上 / 中 / 下三册）做成可检索、可问答的本地 RAG 知识库。

## 怎么发给同事

对方默认已经有教材原文，因此压缩包**不包含 PDF**，只含程序、已抽取文本和向量索引。

1. 在本文件夹双击 **`打包发送.bat`**，生成 `氟化工生产技术知识库.zip`。
2. 把这个 zip 发给对方（U 盘、内网、邮件均可）。
3. 对方解压后阅读 **`给同事.txt`**，或按下面「别人怎么用」操作。

不要把 `.venv` 和 `.env` 发出去。教材 PDF 由对方自己准备即可。

## 别人怎么用

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（勾选 Add Python to PATH）。
2. 解压本文件夹，双击 **`启动知识库.bat`**。
3. 第一次会自动创建虚拟环境并安装依赖，随后浏览器打开问答页面。
4. 在左侧填入大模型 API Key（推荐 [DeepSeek](https://platform.deepseek.com)，也支持通义千问、Kimi、硅基流动、OpenAI、本地 Ollama）。
5. 没有 Key 也可以勾选 **「仅检索原文」**，直接看教材相关段落。
6. 左侧 **「随时补充资料」** 可粘贴文本或上传 txt / md / pdf，加入后会自动切分并重建向量库；删除某条也会立刻更新检索。

macOS / Linux 用户在本目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 这里用了什么 RAG

1. **解析**：上册抽文本，中/下册 OCR，结果在 `data/extracted/`。
2. **切分**：按章节切成约 700 字的知识片段，带册别、章节、页码。
3. **向量库**：对片段做 jieba 分词后建立 TF-IDF 向量（`data/index/vectors.npz`），并与 BM25 做混合检索。
4. **生成**：用检索到的片段归纳回答；「知识片段」展示命中的原文，与回答分开。填写 API Key 后，再把片段交给大模型润色。

## 目录

```
启动知识库.bat          一键启动（Windows）
app.py                  Web 服务
docs/ 或根目录 *.pdf    三册原书
data/extracted/         已抽取的教材文本
data/extracted/extra/   随时加入的补充资料
kb/                     抽取、切分、检索、问答
web/                    页面
```

## 重新入库

若替换了 PDF，或中下册 OCR 中途中断：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-ingest.txt
.venv\Scripts\python.exe -m kb.extract
```

然后在页面点击「重建检索索引」，或重启 `启动知识库.bat`。

## 注意

本知识库仅供内部学习与检索，请勿把教材原文公开上网。回答内容以教材为准，工艺与安全问题请再对照现场规程。

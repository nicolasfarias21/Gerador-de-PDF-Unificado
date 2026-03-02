# api/index.py
import zipfile
from io import BytesIO
from datetime import datetime
from pypdf import PdfReader, PdfWriter
import base64

LIMITE_MB = 90
LIMITE_BYTES = LIMITE_MB * 1024 * 1024

def gerar_log(sucessos, erros, ignorados):
    log = ["===== LOG =====\n"]
    log.append(f"Sucesso: {len(sucessos)}\n")
    log.append(f"Erros: {len(erros)}\n")
    log.append(f"Ignorados: {len(ignorados)}\n")
    return "".join(log)

def handler(request):
    # GET retorna página HTML
    if request.method == "GET":
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Unificador PDFs</title></head>
        <body>
        <h2>Upload de PDFs</h2>
        <form method="post" enctype="multipart/form-data">
        <input type="file" name="files" multiple webkitdirectory><br>
        <button>Processar</button>
        </form>
        </body>
        </html>
        """
        return {"statusCode":200, "headers":{"Content-Type":"text/html"}, "body":html}

    # POST processa arquivos
    arquivos = request.files.getlist("files")
    pdfs_por_pasta = {}
    sucessos, erros, ignorados = [], [], []

    for file in arquivos:
        if not file.filename.lower().endswith(".pdf"):
            continue
        nome_pasta = file.filename.split("/")[0] if "/" in file.filename else "arquivos"
        pdfs_por_pasta.setdefault(nome_pasta, [])
        try:
            conteudo = file.read()
            if not conteudo:
                ignorados.append(file.filename)
                continue
            reader = PdfReader(BytesIO(conteudo), strict=False)
            if len(reader.pages) == 0:
                ignorados.append(file.filename)
                continue
            pdfs_por_pasta[nome_pasta].append(reader)
            sucessos.append(file.filename)
        except Exception as e:
            erros.append(f"{file.filename} -> {e}")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for pasta, readers in pdfs_por_pasta.items():
            todas_paginas = [p for r in readers for p in r.pages]
            parte = 1
            writer = PdfWriter()
            for page in todas_paginas:
                writer.add_page(page)
                temp_buffer = BytesIO()
                writer.write(temp_buffer)
                if temp_buffer.tell() >= LIMITE_BYTES:
                    temp_buffer.seek(0)
                    zipf.writestr(f"{pasta}.pdf" if parte==1 else f"{pasta}_pt{parte}.pdf", temp_buffer.read())
                    parte += 1
                    writer = PdfWriter()
            if writer.pages:
                temp_buffer = BytesIO()
                writer.write(temp_buffer)
                temp_buffer.seek(0)
                zipf.writestr(f"{pasta}.pdf" if parte==1 else f"{pasta}_pt{parte}.pdf", temp_buffer.read())

        zipf.writestr("log.txt", gerar_log(sucessos, erros, ignorados))

    zip_buffer.seek(0)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/zip",
            "Content-Disposition": "attachment; filename=resultado.zip"
        },
        "body": base64.b64encode(zip_buffer.read()).decode(),
        "isBase64Encoded": True
    }

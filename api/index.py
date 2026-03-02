import zipfile
from io import BytesIO
from datetime import datetime
from pypdf import PdfReader, PdfWriter

LIMITE_MB = 90
LIMITE_BYTES = LIMITE_MB * 1024 * 1024

def gerar_log(sucessos, erros, ignorados):
    log = []
    log.append("===== RESUMO DO PROCESSAMENTO =====\n")
    log.append(f"Data/Hora: {datetime.now()}\n\n")
    log.append(f"Total com sucesso: {len(sucessos)}\n")
    log.append(f"Total com erro: {len(erros)}\n")
    log.append(f"Total ignorados: {len(ignorados)}\n\n")

    if erros:
        log.append("Arquivos com erro:\n")
        for e in erros:
            log.append(f"- {e}\n")
        log.append("\n")

    log.append("===== DETALHAMENTO =====\n\n")

    if sucessos:
        log.append("Processados com sucesso:\n")
        for s in sucessos:
            log.append(f"- {s}\n")
        log.append("\n")

    if ignorados:
        log.append("Arquivos ignorados:\n")
        for i in ignorados:
            log.append(f"- {i}\n")
        log.append("\n")

    return "".join(log)


def handler(request):
    if request.method == "POST":
        arquivos = request.files.getlist("files")

        pdfs_por_pasta = {}
        sucessos = []
        erros = []
        ignorados = []

        for file in arquivos:
            if not file.filename.lower().endswith(".pdf"):
                continue

            caminho_relativo = file.filename.replace("\\", "/")
            partes = caminho_relativo.split("/")

            nome_pasta = partes[0] if len(partes) > 1 else "arquivos"

            if nome_pasta not in pdfs_por_pasta:
                pdfs_por_pasta[nome_pasta] = []

            try:
                conteudo = file.read()
                if not conteudo:
                    ignorados.append(f"{caminho_relativo} (vazio)")
                    continue

                pdf_bytesio = BytesIO(conteudo)
                pdf_bytesio.seek(0)

                try:
                    reader = PdfReader(pdf_bytesio, strict=False)
                except Exception as e:
                    ignorados.append(f"{caminho_relativo} (corrompido ou inválido: {e})")
                    continue

                if len(reader.pages) == 0:
                    ignorados.append(f"{caminho_relativo} (sem páginas)")
                    continue

                pdfs_por_pasta[nome_pasta].append(reader)
                sucessos.append(caminho_relativo)

            except Exception as e:
                erros.append(f"{caminho_relativo} -> {str(e)}")

        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for pasta, readers in pdfs_por_pasta.items():
                if not readers:
                    continue

                # Junta todas as páginas
                todas_paginas = []
                for reader in readers:
                    todas_paginas.extend(reader.pages)

                parte = 1
                writer = PdfWriter()
                for page in todas_paginas:
                    writer.add_page(page)
                    temp_buffer = BytesIO()
                    writer.write(temp_buffer)

                    if temp_buffer.tell() >= LIMITE_BYTES:
                        temp_buffer.seek(0)
                        nome_arquivo = f"{pasta}.pdf" if parte == 1 else f"{pasta}_pt{parte}.pdf"
                        zipf.writestr(nome_arquivo, temp_buffer.read())
                        parte += 1
                        writer = PdfWriter()  # reinicia

                # Salva restante
                if len(writer.pages) > 0:
                    temp_buffer = BytesIO()
                    writer.write(temp_buffer)
                    temp_buffer.seek(0)
                    nome_arquivo = f"{pasta}.pdf" if parte == 1 else f"{pasta}_pt{parte}.pdf"
                    zipf.writestr(nome_arquivo, temp_buffer.read())

            # Log sempre
            log_conteudo = gerar_log(sucessos, erros, ignorados)
            zipf.writestr("log_processamento.txt", log_conteudo)

        zip_buffer.seek(0)
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/zip",
                "Content-Disposition": "attachment; filename=resultado.zip"
            },
            "body": zip_buffer.getvalue(),
            "isBase64Encoded": True
        }

    # GET — retorna HTML
    html = open("index.html", "r", encoding="utf-8").read()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html
    }

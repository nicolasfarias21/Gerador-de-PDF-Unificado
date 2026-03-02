import zipfile
from io import BytesIO
from datetime import datetime
from pypdf import PdfReader, PdfWriter

LIMITE_MB = 90
LIMITE_BYTES = LIMITE_MB * 1024 * 1024

def handler(request, context):
    try:
        files = request.files.getlist("files")
    except Exception:
        return {"status": 400, "body": "Nenhum arquivo enviado"}

    pdfs_por_pasta = {}
    sucessos, erros, ignorados = [], [], []

    for file in files:
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
                ignorados.append(f"{caminho_relativo} (corrompido: {e})")
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

            todas_paginas = []
            for reader in readers:
                todas_paginas.extend(reader.pages)

            writer = PdfWriter()
            parte = 1

            for page in todas_paginas:
                writer.add_page(page)
                temp_buffer = BytesIO()
                writer.write(temp_buffer)

                if temp_buffer.tell() > LIMITE_BYTES:
                    # Remove última página adicionada
                    writer.pages.pop()
                    final_buffer = BytesIO()
                    writer.write(final_buffer)
                    final_buffer.seek(0)

                    nome_arquivo = f"{pasta}.pdf" if parte == 1 else f"{pasta}_pt{parte}.pdf"
                    zipf.writestr(nome_arquivo, final_buffer.read())

                    parte += 1
                    writer = PdfWriter()
                    writer.add_page(page)

            # Salva restante
            if len(writer.pages) > 0:
                final_buffer = BytesIO()
                writer.write(final_buffer)
                final_buffer.seek(0)

                nome_arquivo = f"{pasta}.pdf" if parte == 1 else f"{pasta}_pt{parte}.pdf"
                zipf.writestr(nome_arquivo, final_buffer.read())

        # Log sempre
        log_conteudo = gerar_log(sucessos, erros, ignorados)
        zipf.writestr("log_processamento.txt", log_conteudo)

    zip_buffer.seek(0)
    return {
        "status": 200,
        "headers": {
            "Content-Type": "application/zip",
            "Content-Disposition": "attachment; filename=resultado.zip"
        },
        "body": zip_buffer.getvalue()
    }


def gerar_log(sucessos, erros, ignorados):
    log = ["===== RESUMO DO PROCESSAMENTO =====\n"]
    log.append(f"Data/Hora: {datetime.now()}\n\n")
    log.append(f"Total com sucesso: {len(sucessos)}\n")
    log.append(f"Total com erro: {len(erros)}\n")
    log.append(f"Total ignorados: {len(ignorados)}\n\n")

    if erros:
        log.append("Arquivos com erro:\n")
        log.extend([f"- {e}\n" for e in erros])
        log.append("\n")

    log.append("===== DETALHAMENTO =====\n\n")
    if sucessos:
        log.append("Processados com sucesso:\n")
        log.extend([f"- {s}\n" for s in sucessos])
        log.append("\n")
    if ignorados:
        log.append("Arquivos ignorados:\n")
        log.extend([f"- {i}\n" for i in ignorados])
        log.append("\n")
    return "".join(log)

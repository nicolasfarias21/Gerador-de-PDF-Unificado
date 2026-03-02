import zipfile
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, send_file
from pypdf import PdfReader, PdfWriter

app = Flask(__name__, template_folder="../templates")


@app.route("/", methods=["GET", "POST"])
def index():
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

            # Se não vier pasta, agrupa tudo em "arquivos"
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
                    # strict=False ignora cabeçalhos problemáticos e pequenos erros de PDF
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

                writer = PdfWriter()

                for reader in readers:
                    for page in reader.pages:
                        writer.add_page(page)

                pdf_bytes = BytesIO()
                writer.write(pdf_bytes)
                pdf_bytes.seek(0)

                zipf.writestr(f"{pasta}.pdf", pdf_bytes.read())

            # adiciona log sempre
            log_conteudo = gerar_log(sucessos, erros, ignorados)
            zipf.writestr("log_processamento.txt", log_conteudo)

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name="resultado.zip",
            mimetype="application/zip"
        )

    return render_template("index.html")


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

    if erros:
        log.append("Erros detalhados:\n")
        for e in erros:
            log.append(f"- {e}\n")

    return "".join(log)


# obrigatório para Vercel
def handler(request, *args, **kwargs):
    return app(request.environ, lambda *a, **k: None)

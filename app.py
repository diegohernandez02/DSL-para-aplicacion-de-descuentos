"""
Etapa 1 - Aplicación web (Flask) del proyecto:
DSL para reglas de descuento dinámico en e-commerce/retail.

Contiene el enunciado del proyecto, un bloque para escribir o subir el lenguaje
(con un ejemplo digitado) y, a partir de esa entrada, genera los TOKENS y LEXEMAS.
"""
from flask import Flask, render_template, request

from lexer import agrupar, tokenizar

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024  # rechaza cargas de más de 200 KB

LIMITE_ARCHIVO = 100 * 1024  # 100 KB de código DSL es más que suficiente

# Ajusta estos textos al título y planteamiento finales de tu informe.
ENUNCIADO = {
    "titulo": (
        "Implementación de un lenguaje de dominio específico para reglas de descuento "
        "en la validación automática de promociones en una empresa de comercio "
        "electrónico de Lima, 2026"
    ),
    "problema": (
        "En las plataformas de comercio electrónico, las reglas de descuento suelen "
        "estar codificadas dentro del sistema. Cada cambio promocional depende del "
        "equipo de TI y de un nuevo despliegue, y la falta de validación formal permite "
        "reglas ambiguas o que se solapan sobre una misma compra."
    ),
    "vacio": (
        "Falta un lenguaje de dominio específico formalizado con el que las áreas "
        "comerciales definan reglas de descuento complejas sin redesplegar código ni "
        "depender de TI, evitando colisiones y ambigüedades."
    ),
    "objetivo": (
        "Determinar el efecto de un DSL para reglas de descuento sobre la validación "
        "automática y la consistencia de las promociones aplicadas."
    ),
    "proceso": (
        "Evaluación y aplicación automática de promociones empresariales: el área "
        "comercial escribe la regla, el analizador la valida y el sistema la aplica."
    ),
}

EJEMPLO = """SI CLIENTE.nivel = VIP Y COMPRA.total > 500 Y TIEMPO(enrango) ENTONCES APLICAR DESCUENTO(15%)
SINO SI COMPRA.total > 300 ENTONCES APLICAR DESCUENTO(10%)
SINO APLICAR DESCUENTO(0%)
"""


@app.route("/", methods=["GET", "POST"])
def index():
    texto = EJEMPLO
    resultado = None
    error = None

    if request.method == "POST":
        archivo = request.files.get("archivo")
        if archivo and archivo.filename:
            datos = archivo.read(LIMITE_ARCHIVO + 1)
            if len(datos) > LIMITE_ARCHIVO:
                error = "El archivo supera los 100 KB permitidos."
            else:
                try:
                    texto = datos.decode("utf-8-sig")
                except UnicodeDecodeError:
                    error = "El archivo debe estar codificado en UTF-8."
        else:
            texto = request.form.get("codigo", "")

        if error is None:
            if texto.strip():
                analisis = tokenizar(texto)
                resultado = {
                    "tokens": analisis["tokens"],
                    "errores": analisis["errores"],
                    "grupos": agrupar(analisis["tokens"]),
                }
            else:
                error = "Escribe una regla o sube un archivo para analizar."

    return render_template(
        "index.html",
        enunciado=ENUNCIADO,
        texto=texto,
        ejemplo=EJEMPLO,
        resultado=resultado,
        error=error,
    )


@app.errorhandler(413)
def archivo_muy_grande(_):
    return render_template(
        "index.html",
        enunciado=ENUNCIADO,
        texto=EJEMPLO,
        ejemplo=EJEMPLO,
        resultado=None,
        error="El archivo es demasiado grande (máximo 200 KB).",
    ), 413


if __name__ == "__main__":
    app.run()

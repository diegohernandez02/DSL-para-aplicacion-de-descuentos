"""
Aplicación web (Flask) del proyecto:
DSL para reglas de descuento dinámico en e-commerce/retail.

Integra análisis léxico, sintáctico, semántico y generación de objeto JSON
estructurado (sin conexión a servidor transaccional externo).
"""
from flask import Flask, Response, render_template, request

from generador_json import GeneradorJSONReglas
from lexer import agrupar, tokenizar
from parser_meta import MetacompiladorSintactico
from semantico import AnalizadorSemantico

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024

LIMITE_ARCHIVO = 100 * 1024

ENUNCIADO = {
    "titulo": (
        "Implementación de un compilador DSL de reglas de descuento para automatizar "
        "la validación de promociones en una empresa de comercio electrónico en Lima"
    ),
    "problema": (
        "En las plataformas de comercio electrónico, las reglas de descuento suelen "
        "estar codificadas dentro del sistema. Cada cambio promocional depende del "
        "equipo de TI y de un nuevo despliegue, y la falta de validación formal permite "
        "reglas ambiguas o que se solapan sobre una misma compra."
    ),
    "vacio": (
        "Falta de mecanismos formales y automatizados para definir y validar reglas "
        "de descuento y promociones en el rubro del comercio electrónico, generando "
        "baja autonomía comercial y riesgo de ambigüedades o colisiones."
    ),
    "objetivo": (
        "Determinar el efecto de un compilador DSL web de reglas de descuento en la "
        "validación de promociones de una empresa de comercio electrónico en Lima."
    ),
    "proceso": (
        "Definición declarativa de la regla promocional, validación léxica, sintáctica "
        "y semántica, y generación de un objeto JSON estructurado listo para consumo externo."
    ),
}

EJEMPLO = """SI CLIENTE.nivel = VIP Y COMPRA.total > 500 Y TIEMPO(enrango) ENTONCES APLICAR DESCUENTO(15%)
SINO SI COMPRA.total > 300 ENTONCES APLICAR DESCUENTO(10%)
SINO APLICAR DESCUENTO(0%)
"""

TIPOS_ATRIBUTO = {
    ("CLIENTE", "nivel"): "cadena / categoría",
    ("CLIENTE", "puntos"): "numérico",
    ("CLIENTE", "compras"): "numérico",
    ("CLIENTE", "antiguedad"): "numérico",
    ("COMPRA", "total"): "numérico (moneda)",
    ("COMPRA", "cantidad"): "numérico",
    ("COMPRA", "categoria"): "cadena / categoría",
}

metacompilador_sintactico = MetacompiladorSintactico()
analizador_semantico = AnalizadorSemantico()


def _construir_tabla_semantica(arbol: dict | None) -> list[dict]:
    """Extrae lexemas relevantes y su tipo de dato inferido desde el árbol sintáctico."""
    if not arbol:
        return []

    simbolos: list[dict] = []
    vistos: set[tuple[str, str]] = set()

    def agregar(nombre: str, tipo: str) -> None:
        clave = (nombre, tipo)
        if nombre and clave not in vistos:
            vistos.add(clave)
            simbolos.append({"nombre": nombre, "tipo": tipo})

    def recorrer(nodo: dict) -> None:
        if not isinstance(nodo, dict):
            return

        if nodo.get("nodo") == "COMPARACION":
            hijos = nodo.get("hijos", [])
            if len(hijos) >= 3:
                attr_hijos = hijos[0].get("hijos", [])
                val_hijos = hijos[2].get("hijos", [])
                if len(attr_hijos) >= 3:
                    obj_lex = str(attr_hijos[0].get("lexema", ""))
                    atr_lex = str(attr_hijos[2].get("lexema", ""))
                    if obj_lex:
                        agregar(obj_lex, "entidad")
                    if obj_lex and atr_lex:
                        full_attr = f"{obj_lex}.{atr_lex}"
                        tipo_attr = TIPOS_ATRIBUTO.get((obj_lex, atr_lex), "atributo")
                        agregar(full_attr, tipo_attr)
                if val_hijos:
                    val_nodo = val_hijos[0]
                    v_lex = str(val_nodo.get("lexema", ""))
                    v_tok = val_nodo.get("token", "")
                    if v_tok == "T_NUM":
                        agregar(v_lex, "número")
                    elif v_tok == "T_PORCENTAJE":
                        agregar(v_lex, "porcentaje")
                    elif v_tok == "T_CADENA":
                        agregar(v_lex, "cadena")
                    elif v_tok == "T_ID":
                        agregar(v_lex, "identificador / categoría")

        for h in nodo.get("hijos", []):
            recorrer(h)

    recorrer(arbol)
    return simbolos


def _analizar_entrada(texto: str) -> dict:
    lex = tokenizar(texto)
    valido_lexico = len(lex["errores"]) == 0

    if valido_lexico:
        sint = metacompilador_sintactico.analizar_tokens(lex["tokens"])
    else:
        sint = {
            "valido": False,
            "errores_sintacticos": [],
            "arbol": None,
            "arbol_texto": "",
        }

    if valido_lexico and sint["valido"]:
        sem = analizador_semantico.analizar_arbol(sint["arbol"])
        tabla_semantica = _construir_tabla_semantica(sint["arbol"])
    else:
        sem = {
            "valido_semantico": False,
            "errores_semanticos": [],
            "advertencias_semanticas": [],
        }
        tabla_semantica = []

    compilacion_valida = (
        valido_lexico
        and sint["valido"]
        and sem["valido_semantico"]
    )

    salida_json = (
        GeneradorJSONReglas.generar(sint["arbol"], texto)
        if compilacion_valida
        else {"objeto": None, "json_texto": ""}
    )

    return {
        "tokens": lex["tokens"],
        "errores": lex["errores"],
        "valido_lexico": valido_lexico,
        "grupos": agrupar(lex["tokens"]),
        "valido_sintactico": sint["valido"],
        "errores_sintacticos": sint["errores_sintacticos"],
        "arbol": sint["arbol"],
        "arbol_texto": sint["arbol_texto"],
        "valido_semantico": sem["valido_semantico"],
        "errores_semanticos": sem["errores_semanticos"],
        "advertencias_semanticas": sem["advertencias_semanticas"],
        "tabla_semantica": tabla_semantica,
        "compilacion_valida": compilacion_valida,
        "json_objeto": salida_json["objeto"],
        "json_texto": salida_json["json_texto"],
    }


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
                resultado = _analizar_entrada(texto)
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


@app.route("/descargar-json", methods=["POST"])
def descargar_json():
    texto = request.form.get("codigo_json", "")
    analisis = _analizar_entrada(texto)
    if not analisis["compilacion_valida"]:
        return Response("La regla contiene errores y no puede exportarse a JSON.", status=400)
    return Response(
        analisis["json_texto"],
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=regla_descuento.json"},
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

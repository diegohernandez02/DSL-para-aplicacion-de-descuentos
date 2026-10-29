"""
Analizador léxico del DSL de reglas de descuento.

Convierte el texto de entrada en una lista de tokens (con su lexema y posición)
siguiendo la especificación de tokens del diseño (Etapa 1).

ESPECIFICACION queda separada del algoritmo a propósito: en la Etapa 2 se reutiliza
para mostrar la expresión regular de cada token y construir sus autómatas.
"""
import re

# Palabras reservadas: se reconocen con la regla de identificador y luego se
# reclasifican. Así se aplica "coincidencia más larga" (SINO no se parte en SI + NO)
# y "la palabra reservada gana sobre T_ID".
PALABRAS_RESERVADAS = {
    "SI": "T_SI",
    "SINO": "T_SINO",
    "ENTONCES": "T_ENTONCES",
    "APLICAR": "T_APLICAR",
    "DESCUENTO": "T_DESCUENTO",
    "Y": "T_AND",
    "O": "T_OR",
    "NO": "T_NOT",
    "TIEMPO": "T_TIEMPO",
    "CLIENTE": "T_OBJETO",
    "COMPRA": "T_OBJETO",
}

# (token, expresión regular). El ORDEN resuelve los conflictos:
# T_PORCENTAJE va antes que T_NUM porque "15%" debe ser un solo token.
ESPECIFICACION = [
    ("T_PORCENTAJE", r"[0-9]+%"),
    ("T_NUM", r"[0-9]+"),
    ("T_ID", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("T_RELOP", r"!=|>=|<=|=|>|<"),
    ("T_PUNTO", r"\."),
    ("T_PARI", r"\("),
    ("T_PARD", r"\)"),
]

# Orden de presentación de los tokens (el de la tabla de lexemas del diseño).
ORDEN_TOKENS = [
    "T_SI", "T_SINO", "T_ENTONCES", "T_APLICAR", "T_DESCUENTO",
    "T_AND", "T_OR", "T_NOT", "T_TIEMPO", "T_OBJETO",
    "T_ID", "T_NUM", "T_PORCENTAJE", "T_RELOP",
    "T_PUNTO", "T_PARI", "T_PARD",
]

_MAESTRO = re.compile(
    "|".join(f"(?P<{nombre}>{patron})" for nombre, patron in ESPECIFICACION)
    + r"|(?P<ESPACIO>\s+)"
)


def tokenizar(texto):
    """Devuelve {'tokens': [...], 'errores': [...]}.

    Cada token es {'lexema', 'token', 'linea', 'columna'}.
    Un carácter que no encaja en ningún token se reporta como error léxico
    y el análisis continúa con el siguiente carácter.
    """
    tokens, errores = [], []
    pos, linea, inicio_linea = 0, 1, 0

    while pos < len(texto):
        m = _MAESTRO.match(texto, pos)
        if m is None:
            errores.append({
                "caracter": texto[pos],
                "linea": linea,
                "columna": pos - inicio_linea + 1,
            })
            pos += 1
            continue

        tipo, lexema = m.lastgroup, m.group()
        if tipo == "ESPACIO":
            saltos = lexema.count("\n")
            if saltos:
                linea += saltos
                inicio_linea = pos + lexema.rfind("\n") + 1
        else:
            if tipo == "T_ID":
                tipo = PALABRAS_RESERVADAS.get(lexema, "T_ID")
            tokens.append({
                "lexema": lexema,
                "token": tipo,
                "linea": linea,
                "columna": pos - inicio_linea + 1,
            })
        pos = m.end()

    return {"tokens": tokens, "errores": errores}


def agrupar(tokens):
    """Agrupa los lexemas (sin repetir) por token, en el orden del diseño.

    Es la tabla "Token (agrupador) | Lexemas". Solo incluye los tokens presentes.
    """
    grupos = {}
    for t in tokens:
        lexemas = grupos.setdefault(t["token"], [])
        if t["lexema"] not in lexemas:
            lexemas.append(t["lexema"])
    return [(nombre, grupos[nombre]) for nombre in ORDEN_TOKENS if nombre in grupos]

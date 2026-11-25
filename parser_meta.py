"""
Analizador sintáctico y generador de árbol para el DSL de reglas de descuento.

Diseñado para trabajar encima de `lexer.py` (que ya genera los tokens y
errores léxicos en la aplicación web), enfocándose únicamente en:
1. Validar la secuencia de tokens contra la GLC del lenguaje.
2. Reportar errores sintácticos con línea, columna, lexema y mensaje.
3. Construir el árbol sintáctico (en estructura jerárquica y en texto).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ErrorSintactico:
    mensaje: str
    linea: int
    columna: int
    lexema: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mensaje": self.mensaje,
            "linea": self.linea,
            "columna": self.columna,
            "lexema": self.lexema,
        }


@dataclass
class NodoSintactico:
    simbolo: str
    hijos: List[Any] = field(default_factory=list)
    lexema: Optional[str] = None
    token: Optional[str] = None
    linea: Optional[int] = None
    columna: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.token is not None:
            return {
                "nodo": self.simbolo,
                "token": self.token,
                "lexema": self.lexema,
                "linea": self.linea,
                "columna": self.columna,
            }
        return {
            "nodo": self.simbolo,
            "hijos": [h.to_dict() if isinstance(h, NodoSintactico) else h for h in self.hijos],
        }

    def to_texto(self, nivel: int = 0) -> str:
        indent = "  " * nivel
        if self.token is not None:
            return f"{indent}{self.simbolo}: '{self.lexema}' ({self.token})"
        lineas = [f"{indent}{self.simbolo}"]
        for h in self.hijos:
            if isinstance(h, NodoSintactico):
                lineas.append(h.to_texto(nivel + 1))
            else:
                lineas.append(f"{indent}  {h}")
        return "\n".join(lineas)


class _FalloSintactico(Exception):
    def __init__(self, error: ErrorSintactico):
        super().__init__(error.mensaje)
        self.error = error


class GeneradorSintactico:
    """Genera una función analizadora sintáctica a partir de producciones GLC."""

    def __init__(self, producciones: Optional[Dict[str, List[List[str]]]] = None):
        self.producciones = producciones or self.gramatica_glc()

    @staticmethod
    def gramatica_glc() -> Dict[str, List[List[str]]]:
        return {
            "PROGRAMA": [["REGLA", "PROGRAMA_TAIL"]],
            "PROGRAMA_TAIL": [["REGLA", "PROGRAMA_TAIL"], []],
            "REGLA": [["T_SI", "CONDICION", "T_ENTONCES", "ACCION", "RESTO"]],
            "RESTO": [
                ["T_SINO", "T_SI", "CONDICION", "T_ENTONCES", "ACCION", "RESTO"],
                ["T_SINO", "ACCION"],
                [],
            ],
            "CONDICION": [["TERMINO", "CONDICION_TAIL"]],
            "CONDICION_TAIL": [["T_OR", "TERMINO", "CONDICION_TAIL"], []],
            "TERMINO": [["FACTOR", "TERMINO_TAIL"]],
            "TERMINO_TAIL": [["T_AND", "FACTOR", "TERMINO_TAIL"], []],
            "FACTOR": [
                ["T_NOT", "FACTOR"],
                ["T_PARI", "CONDICION", "T_PARD"],
                ["COMPARACION"],
                ["FUNCION_TIEMPO"],
            ],
            "COMPARACION": [["ATRIBUTO", "T_RELOP", "OPERANDO"]],
            "ATRIBUTO": [["T_OBJETO", "T_PUNTO", "T_ID"]],
            "FUNCION_TIEMPO": [["T_TIEMPO", "T_PARI", "T_ID", "T_PARD"]],
            "OPERANDO": [["T_ID"], ["T_NUM"], ["T_PORCENTAJE"]],
            "ACCION": [["T_APLICAR", "T_DESCUENTO", "T_PARI", "T_PORCENTAJE", "T_PARD"]],
        }

    def construir_parser(self) -> Callable[[List[Dict[str, Any]]], Tuple[Optional[NodoSintactico], List[ErrorSintactico]]]:
        producciones = self.producciones

        def parsear(tokens: List[Dict[str, Any]]) -> Tuple[Optional[NodoSintactico], List[ErrorSintactico]]:
            pos = 0
            errores: List[ErrorSintactico] = []

            def actual() -> Optional[Dict[str, Any]]:
                return tokens[pos] if pos < len(tokens) else None

            def crear_error(tok: Optional[Dict[str, Any]], msg: str) -> _FalloSintactico:
                if tok is not None:
                    return _FalloSintactico(
                        ErrorSintactico(
                            mensaje=msg,
                            linea=int(tok.get("linea", 1)),
                            columna=int(tok.get("columna", 1)),
                            lexema=str(tok.get("lexema", "")),
                        )
                    )
                if tokens:
                    ult = tokens[-1]
                    linea = int(ult.get("linea", 1))
                    col = int(ult.get("columna", 1)) + len(str(ult.get("lexema", "")))
                else:
                    linea, col = 1, 1
                return _FalloSintactico(
                    ErrorSintactico(mensaje=msg, linea=linea, columna=col, lexema="EOF")
                )

            def consumir(tipo_esperado: str) -> NodoSintactico:
                nonlocal pos
                tok = actual()
                if tok is None or tok.get("token") != tipo_esperado:
                    encontrado = str(tok.get("lexema")) if tok is not None else "fin de entrada"
                    raise crear_error(
                        tok,
                        f"Se esperaba {tipo_esperado} y se encontró '{encontrado}'.",
                    )
                pos += 1
                return NodoSintactico(
                    simbolo=tipo_esperado,
                    lexema=str(tok.get("lexema", "")),
                    token=str(tok.get("token", "")),
                    linea=int(tok.get("linea", 1)),
                    columna=int(tok.get("columna", 1)),
                )

            def expandir(no_terminal: str) -> NodoSintactico:
                alts = producciones.get(no_terminal)
                if not alts:
                    raise crear_error(actual(), f"No terminal '{no_terminal}' no definido.")

                tok = actual()
                tipo = tok.get("token") if tok is not None else None

                if no_terminal == "PROGRAMA":
                    elegida = alts[0]
                elif no_terminal == "PROGRAMA_TAIL":
                    elegida = alts[0] if tipo == "T_SI" else alts[1]
                elif no_terminal == "RESTO":
                    if tipo == "T_SINO":
                        sig = tokens[pos + 1].get("token") if pos + 1 < len(tokens) else None
                        elegida = alts[0] if sig == "T_SI" else alts[1]
                    else:
                        elegida = alts[2]
                elif no_terminal == "CONDICION":
                    elegida = alts[0]
                elif no_terminal == "CONDICION_TAIL":
                    elegida = alts[0] if tipo == "T_OR" else alts[1]
                elif no_terminal == "TERMINO":
                    elegida = alts[0]
                elif no_terminal == "TERMINO_TAIL":
                    elegida = alts[0] if tipo == "T_AND" else alts[1]
                elif no_terminal == "FACTOR":
                    if tipo == "T_NOT":
                        elegida = alts[0]
                    elif tipo == "T_PARI":
                        elegida = alts[1]
                    elif tipo == "T_OBJETO":
                        elegida = alts[2]
                    elif tipo == "T_TIEMPO":
                        elegida = alts[3]
                    else:
                        encontrado = str(tok.get("lexema")) if tok is not None else "fin de entrada"
                        raise crear_error(tok, f"Se esperaba una condición válida, no '{encontrado}'.")
                elif no_terminal == "OPERANDO":
                    if tipo in ("T_ID", "T_NUM", "T_PORCENTAJE"):
                        elegida = [tipo]
                    else:
                        encontrado = str(tok.get("lexema")) if tok is not None else "fin de entrada"
                        raise crear_error(tok, f"Se esperaba un operando (ID, NUM o PORCENTAJE), no '{encontrado}'.")
                else:
                    elegida = alts[0]

                hijos = [consumir(s) if s.startswith("T_") else expandir(s) for s in elegida]
                return NodoSintactico(simbolo=no_terminal, hijos=hijos)

            if not tokens:
                errores.append(
                    ErrorSintactico(
                        mensaje="No hay tokens válidos para analizar sintácticamente.",
                        linea=1,
                        columna=1,
                        lexema="EOF",
                    )
                )
                return None, errores

            try:
                arbol = expandir("PROGRAMA")
                if actual() is not None:
                    sobrante = actual()
                    raise crear_error(
                        sobrante,
                        f"Token inesperado '{sobrante.get('lexema')}' tras completar la regla.",
                    )
                return arbol, errores
            except _FalloSintactico as exc:
                errores.append(exc.error)
                return None, errores

        return parsear


class MetacompiladorSintactico:
    """Genera y ejecuta el analizador sintáctico sobre los tokens producidos por `lexer.py`."""

    def __init__(self, producciones: Optional[Dict[str, List[List[str]]]] = None):
        self.generador = GeneradorSintactico(producciones=producciones)
        self._parser = self.generador.construir_parser()

    def analizar_tokens(self, tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
        arbol, errores = self._parser(tokens)
        return {
            "valido": len(errores) == 0 and arbol is not None,
            "errores_sintacticos": [e.to_dict() for e in errores],
            "arbol": arbol.to_dict() if arbol else None,
            "arbol_texto": arbol.to_texto() if arbol else "",
        }


if __name__ == "__main__":
    # Ejemplo rápido usando tokens en el formato que entrega `lexer.py`
    from lexer import tokenizar

    ejemplo = "SI CLIENTE.nivel = VIP Y COMPRA.total > 500 Y TIEMPO(enrango) ENTONCES APLICAR DESCUENTO(15%)"
    lex_res = tokenizar(ejemplo)
    meta_sint = MetacompiladorSintactico()
    sint_res = meta_sint.analizar_tokens(lex_res["tokens"])

    print("Válido sintácticamente:", sint_res["valido"])
    print("Errores sintácticos:", sint_res["errores_sintacticos"])
    print("Árbol sintáctico:\n" + sint_res["arbol_texto"])

"""
Módulo de metacompilación para el DSL de reglas de descuento.

Permite:
1. Generar automáticamente el analizador léxico y sintáctico a partir de una
   gramática ANTLR4 (.g4) invocando `antlr4` (si está instalado en el sistema).
2. Proveer un motor de metacompilación / generador de analizador descendente
   en Python puro a partir de las reglas de producción GLC (sin depender de
   Java ni de binarios externos), construyendo un árbol sintáctico (AST/CST)
   y reportando errores léxicos o sintácticos con línea y columna.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


DEFAULT_GRAMMAR_G4 = """grammar Descuentos;

programa
    : regla+ EOF
    ;

regla
    : T_SI condicion T_ENTONCES accion resto
    ;

resto
    : T_SINO T_SI condicion T_ENTONCES accion resto   # RestoSinoSi
    | T_SINO accion                                   # RestoSinoFinal
    |                                                 # RestoVacio
    ;

condicion
    : condicion T_OR termino                          # CondicionOr
    | termino                                         # CondicionTermino
    ;

termino
    : termino T_AND factor                            # TerminoAnd
    | factor                                          # TerminoFactor
    ;

factor
    : T_NOT factor                                    # FactorNot
    | T_PARI condicion T_PARD                         # FactorAgrupado
    | comparacion                                     # FactorComparacion
    | funcionTiempo                                   # FactorFuncionTiempo
    ;

comparacion
    : atributo T_RELOP operando
    ;

atributo
    : T_OBJETO T_PUNTO T_ID
    ;

funcionTiempo
    : T_TIEMPO T_PARI T_ID T_PARD
    ;

operando
    : T_ID                                            # OperandoId
    | T_NUM                                           # OperandoNum
    | T_PORCENTAJE                                    # OperandoPorcentaje
    | T_CADENA                                        # OperandoCadena
    ;

accion
    : T_APLICAR T_DESCUENTO T_PARI T_PORCENTAJE T_PARD
    ;

T_SI        : 'SI' ;
T_SINO      : 'SINO' ;
T_ENTONCES  : 'ENTONCES' ;
T_APLICAR   : 'APLICAR' ;
T_DESCUENTO : 'DESCUENTO' ;
T_AND       : 'Y' ;
T_OR        : 'O' ;
T_NOT       : 'NO' ;
T_OBJETO    : 'CLIENTE' | 'COMPRA' ;
T_TIEMPO    : 'TIEMPO' ;

T_RELOP     : '==' | '!=' | '>=' | '<=' | '=' | '>' | '<' ;

T_PUNTO     : '.' ;
T_PARI      : '(' ;
T_PARD      : ')' ;

T_PORCENTAJE: [0-9]+ ('.' [0-9]+)? '%' ;
T_NUM       : [0-9]+ ('.' [0-9]+)? ;
T_CADENA    : '"' (~["\\r\\n])* '"' | '\'' (~['\\r\\n])* '\'' ;
T_ID        : [a-zA-Z_] [a-zA-Z0-9_]* ;

WS          : [ \\t\\r\\n]+ -> skip ;
COMMENT     : '//' ~[\\r\\n]* -> skip ;
"""


@dataclass
class Token:
    tipo: str
    lexema: str
    linea: int
    columna: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.tipo,
            "lexema": self.lexema,
            "linea": self.linea,
            "columna": self.columna,
        }


@dataclass
class ErrorCompilacion:
    fase: str  # "LEXICO" | "SINTACTICO" | "METACOMPILADOR"
    mensaje: str
    linea: int
    columna: int
    lexema: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fase": self.fase,
            "mensaje": self.mensaje,
            "linea": self.linea,
            "columna": self.columna,
            "lexema": self.lexema,
        }


@dataclass
class NodoArbol:
    simbolo: str
    hijos: List[Any] = field(default_factory=list)
    token: Optional[Token] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.token is not None:
            return {
                "nodo": self.simbolo,
                "lexema": self.token.lexema,
                "token": self.token.tipo,
                "linea": self.token.linea,
                "columna": self.token.columna,
            }
        return {
            "nodo": self.simbolo,
            "hijos": [h.to_dict() if isinstance(h, NodoArbol) else h for h in self.hijos],
        }

    def to_texto(self, nivel: int = 0) -> str:
        indent = "  " * nivel
        if self.token is not None:
            return f"{indent}{self.simbolo}: '{self.token.lexema}' ({self.token.tipo})"
        lineas = [f"{indent}{self.simbolo}"]
        for h in self.hijos:
            if isinstance(h, NodoArbol):
                lineas.append(h.to_texto(nivel + 1))
            else:
                lineas.append(f"{indent}  {h}")
        return "\n".join(lineas)


class ErrorSintacticoInterno(Exception):
    def __init__(self, error: ErrorCompilacion):
        super().__init__(error.mensaje)
        self.error = error


class GeneradorAnalizador:
    """Genera analizadores léxico y sintáctico a partir de una gramática GLC."""

    PALABRAS_RESERVADAS: Dict[str, str] = {
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

    ESPECIFICACION_LEXICA: List[Tuple[str, str]] = [
        ("T_PORCENTAJE", r"[0-9]+(?:\.[0-9]+)?%"),
        ("T_NUM", r"[0-9]+(?:\.[0-9]+)?"),
        ("T_CADENA", r'"[^"\r\n]*"|\'[^\'\r\n]*\''),
        ("T_ID", r"[A-Za-z_][A-Za-z0-9_]*"),
        ("T_RELOP", r"==|!=|>=|<=|=|>|<"),
        ("T_PUNTO", r"\."),
        ("T_PARI", r"\("),
        ("T_PARD", r"\)"),
    ]

    def __init__(self, producciones: Optional[Dict[str, List[List[str]]]] = None):
        self.producciones = producciones or self.gramatica_por_defecto()
        self._regex_maestro = re.compile(
            "|".join(f"(?P<{nombre}>{patron})" for nombre, patron in self.ESPECIFICACION_LEXICA)
            + r"|(?P<COMENTARIO>//[^\r\n]*)|(?P<ESPACIO>\s+)"
        )

    @staticmethod
    def gramatica_por_defecto() -> Dict[str, List[List[str]]]:
        """Devuelve las reglas de producción GLC en forma LL(1) / descendente recursiva."""
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
            "OPERANDO": [["T_ID"], ["T_NUM"], ["T_PORCENTAJE"], ["T_CADENA"]],
            "ACCION": [["T_APLICAR", "T_DESCUENTO", "T_PARI", "T_PORCENTAJE", "T_PARD"]],
        }

    def tokenizar(self, codigo: str) -> Tuple[List[Token], List[ErrorCompilacion]]:
        tokens: List[Token] = []
        errores: List[ErrorCompilacion] = []
        pos = 0
        linea = 1
        inicio_linea = 0

        while pos < len(codigo):
            match = self._regex_maestro.match(codigo, pos)
            if match is None:
                col = pos - inicio_linea + 1
                car = codigo[pos]
                errores.append(
                    ErrorCompilacion(
                        fase="LEXICO",
                        mensaje=f"Carácter inesperado '{car}' fuera del alfabeto del lenguaje.",
                        linea=linea,
                        columna=col,
                        lexema=car,
                    )
                )
                pos += 1
                continue

            grupo = match.lastgroup
            lexema = match.group()
            col = pos - inicio_linea + 1

            if grupo == "ESPACIO" or grupo == "COMENTARIO":
                saltos = lexema.count("\n")
                if saltos:
                    linea += saltos
                    inicio_linea = pos + lexema.rfind("\n") + 1
            elif grupo is not None:
                tipo_token = grupo
                if grupo == "T_ID":
                    tipo_token = self.PALABRAS_RESERVADAS.get(lexema, "T_ID")
                tokens.append(Token(tipo=tipo_token, lexema=lexema, linea=linea, columna=col))

            pos = match.end()

        return tokens, errores

    def construir_parser(self) -> Callable[[List[Token]], Tuple[Optional[NodoArbol], List[ErrorCompilacion]]]:
        """Construye y retorna una función analizadora sintáctica descendente recursiva."""
        producciones = self.producciones

        def parsear(tokens: List[Token]) -> Tuple[Optional[NodoArbol], List[ErrorCompilacion]]:
            indice = 0
            errores: List[ErrorCompilacion] = []

            def actual() -> Optional[Token]:
                return tokens[indice] if indice < len(tokens) else None

            def error_en(tok: Optional[Token], mensaje: str) -> ErrorSintacticoInterno:
                if tok is not None:
                    return ErrorSintacticoInterno(
                        ErrorCompilacion(
                            fase="SINTACTICO",
                            mensaje=mensaje,
                            linea=tok.linea,
                            columna=tok.columna,
                            lexema=tok.lexema,
                        )
                    )
                ultima_linea = tokens[-1].linea if tokens else 1
                ultima_col = (tokens[-1].columna + len(tokens[-1].lexema)) if tokens else 1
                return ErrorSintacticoInterno(
                    ErrorCompilacion(
                        fase="SINTACTICO",
                        mensaje=mensaje,
                        linea=ultima_linea,
                        columna=ultima_col,
                        lexema="EOF",
                    )
                )

            def consumir(tipo_esperado: str) -> NodoArbol:
                nonlocal indice
                tok = actual()
                if tok is None or tok.tipo != tipo_esperado:
                    encontrado = tok.lexema if tok is not None else "fin de entrada (EOF)"
                    raise error_en(
                        tok,
                        f"Se esperaba token {tipo_esperado}, pero se encontró '{encontrado}'.",
                    )
                indice += 1
                return NodoArbol(simbolo=tipo_esperado, token=tok)

            def expandir(no_terminal: str) -> NodoArbol:
                alternativas = producciones.get(no_terminal)
                if not alternativas:
                    raise ErrorSintacticoInterno(
                        ErrorCompilacion(
                            fase="METACOMPILADOR",
                            mensaje=f"No terminal '{no_terminal}' no definido en la gramática.",
                            linea=1,
                            columna=1,
                        )
                    )

                tok = actual()
                tipo_actual = tok.tipo if tok is not None else None

                # Selección predictiva guiada por el token actual y la estructura LL(1)
                elegida: Optional[List[str]] = None

                if no_terminal == "PROGRAMA":
                    elegida = alternativas[0]
                elif no_terminal == "PROGRAMA_TAIL":
                    elegida = alternativas[0] if tipo_actual == "T_SI" else alternativas[1]
                elif no_terminal == "RESTO":
                    if tipo_actual == "T_SINO":
                        siguiente = tokens[indice + 1].tipo if indice + 1 < len(tokens) else None
                        elegida = alternativas[0] if siguiente == "T_SI" else alternativas[1]
                    else:
                        elegida = alternativas[2]
                elif no_terminal == "CONDICION":
                    elegida = alternativas[0]
                elif no_terminal == "CONDICION_TAIL":
                    elegida = alternativas[0] if tipo_actual == "T_OR" else alternativas[1]
                elif no_terminal == "TERMINO":
                    elegida = alternativas[0]
                elif no_terminal == "TERMINO_TAIL":
                    elegida = alternativas[0] if tipo_actual == "T_AND" else alternativas[1]
                elif no_terminal == "FACTOR":
                    if tipo_actual == "T_NOT":
                        elegida = alternativas[0]
                    elif tipo_actual == "T_PARI":
                        elegida = alternativas[1]
                    elif tipo_actual == "T_OBJETO":
                        elegida = alternativas[2]
                    elif tipo_actual == "T_TIEMPO":
                        elegida = alternativas[3]
                    else:
                        encontrado = tok.lexema if tok is not None else "EOF"
                        raise error_en(
                            tok,
                            f"Factor inválido en condición: se encontró '{encontrado}'.",
                        )
                elif no_terminal == "OPERANDO":
                    mapa_operando = {
                        "T_ID": ["T_ID"],
                        "T_NUM": ["T_NUM"],
                        "T_PORCENTAJE": ["T_PORCENTAJE"],
                        "T_CADENA": ["T_CADENA"],
                    }
                    if tipo_actual in mapa_operando:
                        elegida = mapa_operando[tipo_actual]
                    else:
                        encontrado = tok.lexema if tok is not None else "EOF"
                        raise error_en(
                            tok,
                            f"Operando inválido: se encontró '{encontrado}'.",
                        )
                else:
                    elegida = alternativas[0]

                hijos: List[Any] = []
                for simbolo in elegida:
                    if simbolo.startswith("T_"):
                        hijos.append(consumir(simbolo))
                    else:
                        hijos.append(expandir(simbolo))

                return NodoArbol(simbolo=no_terminal, hijos=hijos)

            if not tokens:
                errores.append(
                    ErrorCompilacion(
                        fase="SINTACTICO",
                        mensaje="La entrada no contiene tokens para analizar.",
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
                    raise error_en(
                        sobrante,
                        f"Token inesperado '{sobrante.lexema}' al analizar la regla.",
                    )
                return arbol, errores
            except ErrorSintacticoInterno as exc:
                errores.append(exc.error)
                return None, errores

        return parsear


class MetacompiladorDescuentos:
    """Orquesta la generación del compilador (vía ANTLR4 o generador interno) y compila reglas."""

    def __init__(self, producciones: Optional[Dict[str, List[List[str]]]] = None):
        self.generador = GeneradorAnalizador(producciones=producciones)
        self._parser_fn = self.generador.construir_parser()

    @staticmethod
    def exportar_gramatica_antlr(ruta_salida: str | Path, gramatica: str = DEFAULT_GRAMMAR_G4) -> Path:
        destino = Path(ruta_salida)
        destino.write_text(gramatica, encoding="utf-8")
        return destino

    @staticmethod
    def generar_con_antlr4(ruta_gramatica: str | Path, carpeta_salida: str | Path) -> Dict[str, Any]:
        antlr_bin = shutil.which("antlr4")
        if not antlr_bin:
            return {
                "ejecutado": False,
                "mensaje": (
                    "El comando 'antlr4' no está instalado en el PATH del sistema. "
                    "Se ha conservado la gramática .g4 y el analizador generado en Python."
                ),
            }

        out_dir = Path(carpeta_salida)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [antlr_bin, "-Dlanguage=Python3", "-visitor", "-o", str(out_dir), str(ruta_gramatica)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "ejecutado": True,
            "codigo_salida": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def compilar(self, codigo: str) -> Dict[str, Any]:
        tokens, errores_lexicos = self.generador.tokenizar(codigo)
        if errores_lexicos:
            return {
                "valido": False,
                "fase_fallo": "LEXICO",
                "tokens": [t.to_dict() for t in tokens],
                "errores": [e.to_dict() for e in errores_lexicos],
                "arbol": None,
                "arbol_texto": "",
            }

        arbol, errores_sintacticos = self._parser_fn(tokens)
        if errores_sintacticos or arbol is None:
            return {
                "valido": False,
                "fase_fallo": "SINTACTICO",
                "tokens": [t.to_dict() for t in tokens],
                "errores": [e.to_dict() for e in errores_sintacticos],
                "arbol": None,
                "arbol_texto": "",
            }

        return {
            "valido": True,
            "fase_fallo": None,
            "tokens": [t.to_dict() for t in tokens],
            "errores": [],
            "arbol": arbol.to_dict(),
            "arbol_texto": arbol.to_texto(),
        }


if __name__ == "__main__":
    meta = MetacompiladorDescuentos()
    ruta_g4 = meta.exportar_gramatica_antlr(Path(__file__).with_name("Descuentos.g4"))
    print("Gramática ANTLR4 exportada en:", ruta_g4)

    casos_prueba = [
        "SI CLIENTE.nivel = VIP Y COMPRA.total > 500 Y TIEMPO(enrango) ENTONCES APLICAR DESCUENTO(15%)",
        (
            "SI CLIENTE.nivel = VIP ENTONCES APLICAR DESCUENTO(15%) "
            "SINO SI COMPRA.total > 300 ENTONCES APLICAR DESCUENTO(10%) "
            "SINO APLICAR DESCUENTO(20%)"
        ),
        "SI NO (CLIENTE.categoria == \"NUEVO\" O COMPRA.items >= 3) ENTONCES APLICAR DESCUENTO(12.5%)",
        "SI CLIENTE.nivel = @VIP ENTONCES APLICAR DESCUENTO(10%)",
        "SI CLIENTE.nivel = VIP APLICAR DESCUENTO(10%)",
    ]

    for idx, regla in enumerate(casos_prueba, 1):
        salida = meta.compilar(regla)
        print(f"--- Caso {idx} | Válido: {salida['valido']} ---")
        print("Regla:", regla)
        if salida["errores"]:
            print("Errores:", salida["errores"])
        else:
            print("Árbol:\n" + salida["arbol_texto"])
        print()
